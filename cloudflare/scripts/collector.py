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
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[2]
ORIGINS = {'TPE', 'TSA', 'KHH', 'RMQ'}
DESTINATIONS = {'NRT','HND','KIX','FUK','KMJ','KOJ','OKA','NGO','CTS','SDJ','OKJ','TAK'}
ERROR_TYPES = frozenset({'RATE_LIMITED','UPSTREAM_CHANGED','PARSE_FAILED','TIMEOUT','BLOCKED','SOURCE_UNAVAILABLE','UNKNOWN'})

class SafeFailure(RuntimeError):
    """A deliberately sanitized message suitable for CI logs."""

class AdmissionBlocked(SafeFailure):
    """The calibration receipt does not admit a provider query."""

class ClassifiedFailure(SafeFailure):
    def __init__(self, error_type: str):
        if error_type not in ERROR_TYPES:
            error_type = 'UNKNOWN'
        self.error_type = error_type
        super().__init__('Collection failed')

def classify_failure(exc: BaseException) -> str:
    """Map exceptions to a safe enum without inspecting their messages."""
    declared = getattr(exc, 'error_type', None)
    if isinstance(declared,str) and declared in ERROR_TYPES:
        return declared
    if isinstance(exc, AdmissionBlocked):
        return 'BLOCKED'
    if isinstance(exc, (TimeoutError, socket.timeout, subprocess.TimeoutExpired)):
        return 'TIMEOUT'
    if isinstance(exc, urllib.error.URLError) and isinstance(exc.reason, (TimeoutError, socket.timeout)):
        return 'TIMEOUT'
    status = next((getattr(exc, name, None) for name in ('status_code','status','code')
                   if type(getattr(exc, name, None)) is int), None)
    if status == 429:
        return 'RATE_LIMITED'
    if status in (401,403):
        return 'BLOCKED'
    if status in (404,410):
        return 'UPSTREAM_CHANGED'
    if type(status) is int and 500 <= status <= 599:
        return 'SOURCE_UNAVAILABLE'
    if isinstance(exc, (json.JSONDecodeError, ValueError, TypeError, KeyError, IndexError, AttributeError)):
        return 'PARSE_FAILED'
    if isinstance(exc, (OSError, urllib.error.URLError, ConnectionError)):
        return 'SOURCE_UNAVAILABLE'
    if isinstance(exc, SafeFailure):
        return 'PARSE_FAILED'
    return 'UNKNOWN'

def error_result(error_type: str = 'UNKNOWN') -> dict:
    return {'outcome':'error','error_type':error_type if isinstance(error_type,str) and error_type in ERROR_TYPES else 'UNKNOWN'}

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
    child_env.update(NTFY_ENABLED='false',TELEGRAM_ENABLED='false',PYTHON_DOTENV_DISABLED='1',
                     RADAR_PRIMARY_PROVIDER=os.environ.get('RADAR_PRIMARY_PROVIDER','fast_flights'))
    try:
        result = subprocess.run([sys.executable,str(Path(__file__).with_name('search_once.py'))],
            input=json.dumps(task),text=True,capture_output=True,timeout=90,env=child_env,cwd=ROOT,check=False)
        if result.returncode != 0:
            return error_result('SOURCE_UNAVAILABLE')
        if len(result.stdout) > 16384:
            return error_result('PARSE_FAILED')
        payload = json.loads(result.stdout)
        if not isinstance(payload,dict) or payload.get('outcome') not in {'ok','empty','error'}:
            return error_result('PARSE_FAILED')
        if payload['outcome']=='error':
            return error_result(payload.get('error_type','UNKNOWN'))
        if 'error_type' in payload:
            return error_result('PARSE_FAILED')
        return payload
    except (subprocess.TimeoutExpired,OSError,ValueError) as exc:
        return error_result(classify_failure(exc))

def run_batch(client, search=search_subprocess, max_tasks: int = 3, pause=time.sleep) -> dict:
    if type(max_tasks) is not int or not 1 <= max_tasks <= 3:
        raise SafeFailure('A batch must contain 1-3 tasks')
    client.verify()
    summary = {'run_id':str(uuid.uuid4()),'attempted':0,'observed':0,'errors':0,'error_types':{}}
    for i in range(max_tasks):
        response = client.call('/api/collector/claim',{'run_id':summary['run_id']})
        if response.get('task') is None:
            break
        task = validate_task(response['task'])
        summary['attempted'] += 1
        try:
            payload = search(task)
        except Exception as exc:
            payload = error_result(classify_failure(exc))
        if not isinstance(payload,dict) or payload.get('outcome') not in {'ok','empty','error'}:
            payload = error_result('PARSE_FAILED')
        # Keep fields appropriate to the outcome; never forward exception or provider extras.
        if payload['outcome']=='error':
            payload=error_result(payload.get('error_type','UNKNOWN'))
            summary['error_types'][payload['error_type']]=summary['error_types'].get(payload['error_type'],0)+1
        elif payload['outcome']=='empty':
            payload={'outcome':'empty'}
        elif 'error_type' in payload:
            payload=error_result('PARSE_FAILED')
            summary['error_types']['PARSE_FAILED']=summary['error_types'].get('PARSE_FAILED',0)+1
        else:
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

def require_calibration_admission() -> None:
    gate = ROOT / 'cloudflare' / 'scripts' / 'calibration-gate.mjs'
    try:
        result = subprocess.run(['node',str(gate),'--require-admitted'],capture_output=True,
            text=True,timeout=10,check=False,cwd=ROOT)
    except (OSError,subprocess.TimeoutExpired):
        raise ClassifiedFailure('SOURCE_UNAVAILABLE') from None
    if result.returncode != 0:
        raise AdmissionBlocked('Current calibration decision does not admit collection')

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    parser.add_argument('--max-tasks',type=int,choices=(1,2,3),default=3)
    args = parser.parse_args()
    if not args.execute:
        print(json.dumps({'mode':'dry-run','max_tasks':args.max_tasks,'network_calls':0}))
        return 0
    if os.getenv('RADAR_COLLECTOR_ENABLED') != 'true':
        raise SafeFailure('RADAR_COLLECTOR_ENABLED must explicitly be true')
    require_calibration_admission()
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
