"""Bounded collector. Default CLI mode is dry-run; external access requires --execute.

Uses only a dedicated collector key, never a Cloudflare deployment token. Provider
work happens in a timeout-bounded subprocess. Failures stop the batch; no proxy,
CAPTCHA bypass, automatic retry loop, or notification sending is implemented.
"""
from __future__ import annotations
import argparse
from datetime import date
import json
import os
from pathlib import Path
import re
import site
import subprocess
import sys
import time
from collections.abc import Sequence
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[2]
ORIGINS = {'TPE', 'TSA', 'KHH', 'RMQ'}
DESTINATIONS = {'NRT','HND','KIX','FUK','KMJ','KOJ','OKA','NGO','CTS','SDJ','OKJ','TAK'}
SEARCH_PROVIDERS = {'fast_flights', 'fli', 'fli_custom'}

class SafeFailure(RuntimeError):
    """A deliberately sanitized message suitable for CI logs."""

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SafeFailure('Redirect refused; no credential forwarded')

def validated_origin(url: str) -> str:
    p = urllib.parse.urlsplit(url)
    if p.scheme != 'https' or not p.hostname or p.username or p.password or p.port not in (None,443):
        raise SafeFailure('RADAR_URL must be an HTTPS origin with no credentials')
    if p.path not in ('','/') or p.query or p.fragment:
        raise SafeFailure('RADAR_URL must not include a path, query or fragment')
    return f'https://{p.netloc.lower()}'

class Client:
    def __init__(self, url: str, key: str, role: str = 'collector'):
        self.origin = validated_origin(url)
        if not isinstance(key,str) or not 32 <= len(key) <= 256 or not re.fullmatch(r'[!-~]+',key):
            raise SafeFailure('A dedicated 32-256 character secret is required')
        if role not in {'collector','admin'}:
            raise SafeFailure('Invalid client role')
        self.key,self.role = key,role
        self.opener = urllib.request.build_opener(NoRedirect())

    def call(self, path: str, data: dict | None = None) -> dict:
        allowed = {'/api/health','/api/collector/claim','/api/collector/result','/api/collector/report'}
        if self.role == 'admin':
            allowed = {'/api/health','/api/admin/tasks'}
        if path not in allowed:
            raise SafeFailure('Unexpected API path')
        headers = {'Accept':'application/json',
            'User-Agent':'ai-flight-radar-collector/2.0 (+https://github.com/Reese-max/ai-flight-radar)'}
        if path != '/api/health':
            headers['X-API-Key' if self.role == 'admin' else 'Authorization'] = (
                self.key if self.role == 'admin' else f'Bearer {self.key}')
        raw = None if data is None else json.dumps(data,ensure_ascii=False,separators=(',',':')).encode()
        if raw is not None:
            if len(raw) > 16384:
                raise SafeFailure('Request exceeds local size cap')
            headers['Content-Type'] = 'application/json'
        req = urllib.request.Request(self.origin+path,data=raw,headers=headers,method='GET' if data is None else 'POST')
        try:
            with self.opener.open(req,timeout=20) as response:
                if response.headers.get_content_type() != 'application/json':
                    raise SafeFailure('API returned a non-JSON response')
                body = response.read(65537)
                if len(body) > 65536:
                    raise SafeFailure('API response exceeds size cap')
                result = json.loads(body)
                if not isinstance(result,dict):
                    raise SafeFailure('API response must be an object')
                return result
        except urllib.error.HTTPError as exc:
            raise SafeFailure(f'Radar API HTTP {exc.code}; stopped without retry') from None
        except SafeFailure:
            raise
        except (OSError,ValueError,urllib.error.URLError):
            raise SafeFailure('Radar API connection or JSON failure; stopped without retry') from None

    def verify(self):
        health = self.call('/api/health')
        if health.get('app_id') != 'reese-max/ai-flight-radar:cloudflare-v1' or health.get('schema_version') != 1:
            raise SafeFailure('Radar identity/schema mismatch')

def validate_task(task: dict) -> dict:
    if not isinstance(task,dict) or not re.fullmatch(r'[a-f0-9]{64}',str(task.get('id',''))):
        raise SafeFailure('Invalid task ID')
    try:
        token = str(uuid.UUID(task['lease_token']))
        dep,ret = date.fromisoformat(task['depart_date']),date.fromisoformat(task['return_date'])
    except (ValueError,TypeError,KeyError):
        raise SafeFailure('Invalid task lease or dates') from None
    if task.get('origin') not in ORIGINS or task.get('destination') not in DESTINATIONS or not 1 <= (ret-dep).days <= 30:
        raise SafeFailure('Task is outside configured collection scope')
    return {k:task[k] for k in ('id','origin','destination','depart_date','return_date')} | {'lease_token':token}

def search_subprocess(task: dict) -> dict:
    # Avoid exposing runner/application credentials to the upstream search process.
    keep = {'PATH','HOME','USERPROFILE','SYSTEMROOT','WINDIR','TEMP','TMP','TMPDIR','SSL_CERT_FILE','SSL_CERT_DIR'}
    child_env = {k:v for k,v in os.environ.items() if k.upper() in keep}
    # Winsock (_overlapped/asyncio) fails with WSAEPROVIDERFAILEDINIT unless the
    # env block carries the canonical uppercase SYSTEMROOT.
    child_env['SYSTEMROOT'] = os.environ.get('SYSTEMROOT') or r'C:\Windows'
    # Store Python installs user packages under LocalCache, which site.py cannot
    # locate under a stripped env; hand the child the resolved site dirs instead.
    extra = [p for p in (*site.getsitepackages(), site.getusersitepackages()) if p and os.path.isdir(p)]
    child_env['PYTHONPATH'] = os.pathsep.join(dict.fromkeys(extra))
    primary = (os.environ.get('RADAR_PRIMARY_PROVIDER') or 'fast_flights').strip().lower()
    primary = primary or 'fast_flights'
    fallback = os.environ.get('RADAR_FALLBACK_PROVIDER', '').strip().lower()
    if primary not in SEARCH_PROVIDERS or (fallback and fallback not in SEARCH_PROVIDERS):
        raise SafeFailure('Invalid search provider configuration')
    child_env.update(NTFY_ENABLED='false',TELEGRAM_ENABLED='false',PYTHON_DOTENV_DISABLED='1',
                     RADAR_PRIMARY_PROVIDER=primary)
    if fallback:
        child_env['RADAR_FALLBACK_PROVIDER'] = fallback
    try:
        result = subprocess.run([sys.executable,str(Path(__file__).with_name('search_once.py'))],
            input=json.dumps(task),text=True,capture_output=True,timeout=90,env=child_env,cwd=ROOT,check=False)
        if result.returncode != 0 or len(result.stdout) > 16384:
            return {'outcome':'error'}
        payload = json.loads(result.stdout)
        if not isinstance(payload,dict) or payload.get('outcome') not in {'ok','empty','error'}:
            return {'outcome':'error'}
        return payload
    except (subprocess.TimeoutExpired,OSError,ValueError):
        return {'outcome':'error'}

def cron_runs_per_hour(expression: str) -> int:
    """Scheduled runs per hour for a cron expression that fires every day.

    Fails closed on a cadence this contract cannot reason about, instead of
    guessing a service rate that would silently overstate collector capacity.
    """
    fields = expression.split()
    if len(fields) != 5:
        raise SafeFailure('Collector cron must have five fields')
    minute, hour, day_of_month, month, day_of_week = fields
    if (day_of_month, month, day_of_week) != ('*', '*', '*'):
        raise SafeFailure('Collector cron must run every day')
    def count(field: str, bound: int, name: str) -> int:
        selected = set()
        for value in field.split(','):
            if value == '*':
                selected.update(range(bound))
            elif value.startswith('*/'):
                step = value[2:]
                if not step.isdigit() or int(step) < 1 or bound % int(step):
                    raise SafeFailure(f'Unsupported collector cron {name} step')
                selected.update(range(0, bound, int(step)))
            elif value.isdigit() and 0 <= int(value) < bound:
                selected.add(int(value))
            else:
                raise SafeFailure(f'Unsupported collector cron {name} field')
        return len(selected)
    minutes, hours = count(minute, 60, 'minute'), count(hour, 24, 'hour')
    # Budget windows reset each wall-clock hour. Averaging sparse execution
    # hours before applying that cap would overstate usable capacity.
    if hours != 24:
        raise SafeFailure('Collector cron must serve every hour for this capacity contract')
    return minutes

CRON_PATTERN = re.compile(r"^\s*-\s*cron:\s*['\"]?([^'\"\n]+)['\"]?\s*$", re.MULTILINE)
MAX_TASKS_PATTERN = re.compile(r'--max-tasks\s+(\d+)')
REVISIT_PATTERN = re.compile(r'REVISIT_HOURS\s*=\s*(\d+)')
REVISIT_DERIVATION = 'REVISIT_MS=REVISIT_HOURS*HOUR'
BACKOFF_DERIVATION = 'ERROR_BACKOFF_MS=HOUR'
TTL_DERIVATION = 'TTL=REVISIT_MS'

def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding='utf-8')
    except OSError:
        raise SafeFailure(f'Cannot read {path.name} for the coverage contract') from None

def coverage_plan(root: Path = ROOT, active_routes: int | None = None, revisit_hours: int | None = None,
                  runs_per_hour: int | None = None, max_tasks_per_run: int | None = None,
                  claim_budget: int | None = None) -> dict:
    """Planned coverage demand and planned service capacity, from checked-in files.

    Demand is one revisit of every active route per interval. Capacity is the
    scheduled batches per hour times the bounded tasks per batch, itself capped
    by the deployed hourly claim budget. A configuration where demand exceeds
    capacity starves routes under normal zero-error operation, so it is
    reported as unsustainable instead of being discovered as stale prices.
    """
    if active_routes is None:
        active_routes = len(ORIGINS) * len(DESTINATIONS)
    if type(active_routes) is not int or active_routes < 1:
        raise SafeFailure('Active route count must be a positive integer')
    workflow = _read_text(root / '.github/workflows/collector.yml')
    logic = _read_text(root / 'cloudflare/src/logic.mjs')
    store = _read_text(root / 'cloudflare/src/store.mjs')
    # A generated deploy config is what actually ships, so it wins when present.
    deploy_config = root / 'cloudflare/wrangler.deploy.json'
    budget_source = deploy_config if deploy_config.is_file() else root / 'cloudflare/wrangler.json'
    wrangler = _read_text(budget_source)
    if runs_per_hour is None:
        cron = CRON_PATTERN.search(workflow)
        if not cron:
            raise SafeFailure('Collector workflow has no scheduled batch')
        runs_per_hour = cron_runs_per_hour(cron.group(1).strip())
    if max_tasks_per_run is None:
        batch = MAX_TASKS_PATTERN.search(workflow)
        if not batch:
            raise SafeFailure('Collector workflow has no bounded batch size')
        max_tasks_per_run = int(batch.group(1))
    if type(runs_per_hour) is not int or runs_per_hour < 1:
        raise SafeFailure('Scheduled runs must be a positive integer')
    if type(max_tasks_per_run) is not int or not 1 <= max_tasks_per_run <= 3:
        raise SafeFailure('Scheduled batch size must stay within the bounded 1-3 tasks')
    if revisit_hours is None:
        interval = REVISIT_PATTERN.search(logic)
        derived = all(token in logic.replace(' ','') for token in
                      (REVISIT_DERIVATION,BACKOFF_DERIVATION,TTL_DERIVATION))
        if not interval or not derived or 'REVISIT_MS' not in store or 'ERROR_BACKOFF_MS' not in store:
            raise SafeFailure('Store must reschedule from the shared revisit interval constants')
        revisit_hours = int(interval.group(1))
    if type(revisit_hours) is not int or revisit_hours < 1:
        raise SafeFailure('Revisit interval must be at least one hour')
    if claim_budget is None:
        try:
            config = json.loads(wrangler)
            value = config['vars']['MAX_SEARCHES_PER_HOUR']
        except (ValueError, KeyError, TypeError):
            raise SafeFailure('Deployment has no valid hourly claim budget') from None
        if type(value) is int:
            claim_budget = value
        elif isinstance(value, str) and re.fullmatch(r'[0-9]+', value):
            claim_budget = int(value)
        else:
            raise SafeFailure('Deployment has no valid hourly claim budget')
    if type(claim_budget) is not int or not 1 <= claim_budget <= 10:
        raise SafeFailure('Deployed hourly claim budget must stay within 1-10 searches')
    scheduled = runs_per_hour * max_tasks_per_run
    capacity = min(scheduled, claim_budget)
    demand = active_routes / revisit_hours
    return {'active_routes':active_routes,'revisit_hours':revisit_hours,'runs_per_hour':runs_per_hour,
        'max_tasks_per_run':max_tasks_per_run,'scheduled_claims_per_hour':scheduled,'claim_budget':claim_budget,
        'budget_source':budget_source.name,
        'capacity_per_hour':float(capacity),'demand_per_hour':demand,'headroom_per_hour':round(capacity-demand,6),
        'sustainable':demand <= capacity,
        'invariant':'active routes / revisit hours <= min(runs per hour * max tasks per run, hourly claim budget)'}

def simulate_coverage(active_routes: int, revisit_hours: int, runs_per_hour: int, max_tasks_per_run: int,
                      claim_budget: int, error_backoff_hours: int = 1, windows: int = 2,
                      error_runs: Sequence[int] = ()) -> dict:
    """Deterministic frozen-clock replay of the scheduled collector over the route matrix.

    Mirrors the real claim order (due routes first) and the real failure semantics:
    an ok/empty result reschedules a route one revisit interval later, an error
    stops the rest of that batch and retries the route after the error backoff.
    Every claim request consumes the hourly server budget, including a claim
    with no due task. A rejected claim ends the scheduled batch. `error_runs`
    names absolute run numbers, counting every scheduled run from zero.
    """
    if not all(type(value) is int and value > 0 for value in
               (active_routes,runs_per_hour,max_tasks_per_run,windows,claim_budget)) or revisit_hours < 1 or error_backoff_hours < 1:
        raise SafeFailure('Coverage simulation needs positive integer arguments')
    errors = set(error_runs)
    horizon = revisit_hours * windows
    due = {route:0 for route in range(active_routes)}
    served = {route:0 for route in due}
    last = dict.fromkeys(due)
    gaps = {route:[] for route in due}
    attempts = error_count = budget_rejections = 0
    claims_per_hour = []
    for hour in range(horizon + 1):
        hourly_claims = 0
        for index in range(runs_per_hour):
            now = hour + index / runs_per_hour
            attempts += 1
            for _ in range(max_tasks_per_run):
                if hourly_claims >= claim_budget:
                    budget_rejections += 1
                    break
                hourly_claims += 1
                available = sorted((at, route) for route, at in due.items() if at <= now)
                if not available:
                    break
                route = available[0][1]
                if hour * runs_per_hour + index in errors:
                    error_count += 1
                    due[route] = now + error_backoff_hours
                    break  # An upstream failure ends this batch, exactly like run_batch.
                if served[route]:
                    gaps[route].append(round(now - last[route], 6))
                served[route] += 1
                last[route] = now
                due[route] = now + revisit_hours
        claims_per_hour.append(hourly_claims)
    observed = [gap for values in gaps.values() for gap in values]
    delayed = sorted(route for route, values in gaps.items() if any(gap > revisit_hours for gap in values))
    unserved = sorted(route for route in due if not served[route])
    max_interval = max(observed) if observed else None
    return {'active_routes':active_routes,'revisit_hours':revisit_hours,'runs_per_hour':runs_per_hour,
        'max_tasks_per_run':max_tasks_per_run,'claim_budget':claim_budget,'claims_per_hour':claims_per_hour,
        'max_claims_per_hour':max(claims_per_hour),
        'budget_rejections':budget_rejections,'windows':windows,'horizon_hours':horizon,'batches':attempts,
        'served':sum(served.values()),'errors':error_count,'unserved':unserved,
        'routes_delayed':delayed,'max_interval_hours':max_interval,'degraded':error_count > 0,
        'target_met':error_count == 0 and not unserved and not delayed and max_interval is not None
            and max_interval <= revisit_hours}

def run_batch(client, search=search_subprocess, max_tasks: int = 3, pause=time.sleep) -> dict:
    if type(max_tasks) is not int or not 1 <= max_tasks <= 3:
        raise SafeFailure('A batch must contain 1-3 tasks')
    client.verify()
    summary = {'run_id':str(uuid.uuid4()),'attempted':0,'observed':0,'errors':0}
    for i in range(max_tasks):
        response = client.call('/api/collector/claim',{'run_id':summary['run_id']})
        if response.get('task') is None:
            break
        task = validate_task(response['task'])
        summary['attempted'] += 1
        try:
            payload = search(task)
        except Exception:
            payload = {'outcome':'error'}
        if not isinstance(payload,dict) or payload.get('outcome') not in {'ok','empty','error'}:
            payload = {'outcome':'error'}
        # Client code cannot let a provider override the task or credential context.
        payload = {k:v for k,v in payload.items() if k in {'outcome','price_twd','searched_at','airline','offer_count'}}
        payload.update(task_id=task['id'],lease_token=task['lease_token'])
        accepted = client.call('/api/collector/result',payload)
        if accepted.get('status') != 'accepted':
            raise SafeFailure('Result was not accepted')
        if payload['outcome']=='ok':
            summary['observed'] += 1
        elif payload['outcome']=='error':
            summary['errors'] += 1
            break  # Do not keep searching after an upstream failure/possible limit.
        if i+1 < max_tasks:
            pause(4)
    client.call('/api/collector/report',summary)
    return summary

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--max-tasks',type=int,choices=(1,2,3),default=3)
    parser.add_argument('--check-capacity',action='store_true',
        help='Report planned route coverage against planned collector capacity and exit')
    args = parser.parse_args()
    if args.check_capacity:
        checked = coverage_plan()
        print(json.dumps(checked))
        return 0 if checked['sustainable'] else 3
    if not args.execute:
        print(json.dumps({'mode':'dry-run','max_tasks':args.max_tasks,'network_calls':0}))
        return 0
    if os.getenv('RADAR_COLLECTOR_ENABLED') != 'true':
        raise SafeFailure('RADAR_COLLECTOR_ENABLED must explicitly be true')
    client = Client(os.getenv('RADAR_URL',''),os.getenv('RADAR_COLLECTOR_KEY',''))
    result = run_batch(client,max_tasks=args.max_tasks)
    print(json.dumps(result))
    return 2 if result['errors'] else 0

if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except SafeFailure as exc:
        print(str(exc),file=sys.stderr)
        raise SystemExit(2)
