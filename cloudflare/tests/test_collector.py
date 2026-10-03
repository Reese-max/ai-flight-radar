import contextlib
import ast
from datetime import date
import io
import json
from pathlib import Path
import re
import subprocess
import sys
from types import ModuleType,SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from collector import AdmissionBlocked,Client,NoRedirect,SafeFailure,classify_failure,run_batch,validated_origin,validate_task,search_subprocess
from search_once import normalize
from tasks import plan

def task():
    return {'id':'a'*64,'lease_token':str(uuid.uuid4()),'origin':'TPE','destination':'FUK',
            'depart_date':'2026-11-12','return_date':'2026-11-16'}

def offer(price=5000,**overrides):
    return SimpleNamespace(**({'price_twd':price,'origin':'TPE','destination':'FUK','depart_date':'2026-11-12',
        'return_date':'2026-11-16','trip_type':'round-trip','is_direct':True,'stops':0,'primary_airline':'Synthetic test airline'}|overrides))

class FakeClient:
    def __init__(self,tasks):self.tasks=list(tasks);self.calls=[];self.verified=False
    def verify(self):self.verified=True
    def call(self,path,data=None):
        self.calls.append((path,data))
        if path.endswith('/claim'):return {'task':self.tasks.pop(0) if self.tasks else None}
        if path.endswith('/result'):return {'status':'accepted'}
        return {'recorded':True}

class CollectorTests(unittest.TestCase):
    def test_default_cli_makes_no_network_calls(self):
        module=Path(__file__).resolve().parents[1]/'scripts/collector.py'
        p=subprocess.run([sys.executable,str(module)],capture_output=True,text=True,check=True)
        self.assertEqual(json.loads(p.stdout)['network_calls'],0)
    def test_execute_requires_explicit_environment_gate(self):
        import collector
        with patch.object(sys,'argv',['collector','--execute']),patch.dict('os.environ',{},clear=True):
            with self.assertRaises(SafeFailure):collector.main()
    def test_execute_refuses_current_BLOCK_receipt_before_network(self):
        import collector
        environment={'RADAR_COLLECTOR_ENABLED':'true','RADAR_URL':'https://radar.example','RADAR_COLLECTOR_KEY':'x'*48}
        with patch.object(sys,'argv',['collector','--execute','--max-tasks','1']),patch.dict('os.environ',environment):
            with self.assertRaisesRegex(SafeFailure,'calibration'):
                collector.main()
    def test_single_search_helper_stops_before_provider_when_calibration_blocks(self):
        import collector
        import search_once
        provider_selector=ModuleType('providers.selector')
        provider_selector.get_provider=lambda:self.fail('provider must not run')
        out=io.StringIO()
        with patch.object(sys,'stdin',io.StringIO(json.dumps(task()))),patch.object(sys,'stdout',out),\
            patch('collector.require_calibration_admission',side_effect=AdmissionBlocked('blocked')),\
            patch.dict(sys.modules,{'providers.selector':provider_selector}):
            search_once.main()
        self.assertEqual(json.loads(out.getvalue()),{'outcome':'error','error_type':'BLOCKED'})
    def test_https_only(self):
        with self.assertRaises(SafeFailure):validated_origin('http://radar.example')
    def test_no_credentials_in_url(self):
        with self.assertRaises(SafeFailure):validated_origin('https://user:key@radar.example')
    def test_no_path_or_query(self):
        for url in ['https://radar.example/api','https://radar.example?token=x','https://radar.example#x']:
            with self.subTest(url=url),self.assertRaises(SafeFailure):validated_origin(url)
    def test_redirects_never_forward_credentials(self):
        with self.assertRaises(SafeFailure):NoRedirect().redirect_request(None,None,302,'',{},'https://other.example')
    def test_weak_key_refused(self):
        with self.assertRaises(SafeFailure):Client('https://radar.example','weak')
    def test_unexpected_api_route_refused(self):
        c=Client('https://radar.example','x'*48)
        with self.assertRaises(SafeFailure):c.call('/api/admin/tasks',{})
    def test_max_three_tasks(self):
        c=FakeClient([task() for _ in range(5)])
        summary=run_batch(c,lambda t:{'outcome':'empty'},pause=lambda _:None)
        self.assertEqual(summary['attempted'],3);self.assertTrue(c.verified)
    def test_invalid_batch_size_refused(self):
        for n in [0,4,True]:
            with self.subTest(n=n),self.assertRaises(SafeFailure):run_batch(FakeClient([]),max_tasks=n)
    def test_no_tasks_is_not_successful_collection(self):
        c=FakeClient([]);summary=run_batch(c,lambda _:self.fail('must not search'))
        self.assertEqual(summary['observed'],0)
    def test_provider_error_stops_remaining_tasks(self):
        c=FakeClient([task(),task()]);summary=run_batch(c,lambda _: {'outcome':'error'},pause=lambda _:None)
        self.assertEqual(summary['attempted'],1);self.assertEqual(summary['errors'],1)
        self.assertEqual(summary['error_types'],{'UNKNOWN':1})
        posted=[body for p,body in c.calls if p.endswith('/result')][0]
        self.assertEqual(posted['error_type'],'UNKNOWN')

    def test_typed_provider_failure_is_sanitized_and_reported(self):
        error=RuntimeError('secret upstream body');error.status_code=429
        c=FakeClient([task()]);summary=run_batch(c,lambda _:(_ for _ in ()).throw(error),pause=lambda _:None)
        posted=[body for p,body in c.calls if p.endswith('/result')][0]
        report=[body for p,body in c.calls if p.endswith('/report')][0]
        self.assertEqual(posted['error_type'],'RATE_LIMITED')
        self.assertEqual(report['error_types'],{'RATE_LIMITED':1})
        self.assertNotIn('secret upstream body',json.dumps([posted,report,summary]))

    def test_failure_classifier_maps_statuses_without_reading_error_text(self):
        for status,expected in [(429,'RATE_LIMITED'),(403,'BLOCKED'),(404,'UPSTREAM_CHANGED'),(503,'SOURCE_UNAVAILABLE')]:
            error=RuntimeError('raw provider response');error.status_code=status
            with self.subTest(status=status):self.assertEqual(classify_failure(error),expected)

    def test_invalid_error_metadata_is_reduced_to_unknown_enum(self):
        c=FakeClient([task()]);summary=run_batch(c,lambda _:{'outcome':'error','error_type':['secret'],'response':'raw body'},pause=lambda _:None)
        posted=[body for p,body in c.calls if p.endswith('/result')][0]
        self.assertEqual(posted['error_type'],'UNKNOWN')
        self.assertEqual(set(posted),{'outcome','error_type','task_id','lease_token'})
        self.assertNotIn('raw body',json.dumps(summary))
    def test_provider_cannot_override_task_lease(self):
        original=task();c=FakeClient([original]);run_batch(c,lambda _: {'outcome':'empty','task_id':'evil','lease_token':'evil'},max_tasks=1)
        posted=[body for p,body in c.calls if p.endswith('/result')][0]
        self.assertEqual(posted['task_id'],original['id']);self.assertEqual(posted['lease_token'],original['lease_token'])
    def test_unknown_task_airport_rejected(self):
        with self.assertRaises(SafeFailure):validate_task(task()|{'destination':'XXX'})
    def test_timeout_becomes_error_and_no_raw_trace(self):
        with patch('subprocess.run',side_effect=subprocess.TimeoutExpired('test',90)):
            self.assertEqual(search_subprocess(task()),{'outcome':'error','error_type':'TIMEOUT'})
    def test_child_does_not_receive_application_or_github_secrets(self):
        captured={}
        def fake(*a,**k):captured.update(k);return SimpleNamespace(returncode=0,stdout='{"outcome":"empty"}')
        with patch.dict('os.environ',{'RADAR_COLLECTOR_KEY':'secret','GITHUB_TOKEN':'secret','ADMIN_KEY':'secret'}),patch('subprocess.run',side_effect=fake):
            search_subprocess(task())
        self.assertNotIn('RADAR_COLLECTOR_KEY',captured['env']);self.assertNotIn('GITHUB_TOKEN',captured['env']);self.assertEqual(captured['timeout'],90)
    def test_minimum_valid_offer_selected(self):
        result=normalize([offer(9000),offer(5000)],task())
        self.assertEqual(result['price_twd'],5000);self.assertEqual(result['offer_count'],2)
    def test_zero_and_boolean_fares_rejected(self):
        self.assertEqual(normalize([offer(0),offer(True)],task()),{'outcome':'error','error_type':'PARSE_FAILED'})
    def test_wrong_trip_or_dates_not_saved(self):
        self.assertEqual(normalize([offer(trip_type='one-way'),offer(return_date='2026-11-17')],task()),{'outcome':'error','error_type':'PARSE_FAILED'})
    def test_empty_provider_list_is_empty_not_error_or_free(self):
        self.assertEqual(normalize([],task()),{'outcome':'empty'})
    def test_bad_airline_is_unknown_not_invented(self):
        self.assertIsNone(normalize([offer(primary_airline='bad\nname')],task())['airline'])
    def test_initial_plan_matches_the_configured_calibration_route_matrix(self):
        p=plan(date(2026,9,11));self.assertEqual(len(p['tasks']),16)
        self.assertEqual(p['tasks'][0],{'origin':'TPE','destination':'NRT','depart_date':'2026-10-11','return_date':'2026-10-15'})
        self.assertEqual(len({(t['origin'],t['destination']) for t in p['tasks']}),16)
    def test_task_plan_routes_match_worker_catalog_exactly(self):
        cloudflare=Path(__file__).resolve().parents[1]
        catalog=(cloudflare/'src'/'catalog.mjs').read_text(encoding='utf-8')
        route_block=catalog.split('export const routes = [',1)[1].split('].map',1)[0]
        expected=set(re.findall(r"\['([A-Z]{3})','([A-Z]{3})'\]",route_block))
        module=ast.parse((cloudflare/'scripts'/'tasks.py').read_text(encoding='utf-8'))
        assignment=next(node for node in module.body if isinstance(node,ast.Assign) and
            any(isinstance(target,ast.Name) and target.id=='ROUTES' for target in node.targets))
        actual=set(ast.literal_eval(assignment.value))
        self.assertEqual(actual,expected)
    def test_invalid_plan_duration(self):
        with self.assertRaises(SafeFailure):plan(date(2026,9,11),nights=0)

if __name__=='__main__':unittest.main()
