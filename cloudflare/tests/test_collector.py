import contextlib
from datetime import date
import io
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from collector import Client,NoRedirect,SafeFailure,run_batch,validated_origin,validate_task,search_subprocess
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
    def test_provider_cannot_override_task_lease(self):
        original=task();c=FakeClient([original]);run_batch(c,lambda _: {'outcome':'empty','task_id':'evil','lease_token':'evil'},max_tasks=1)
        posted=[body for p,body in c.calls if p.endswith('/result')][0]
        self.assertEqual(posted['task_id'],original['id']);self.assertEqual(posted['lease_token'],original['lease_token'])
    def test_unknown_task_airport_rejected(self):
        with self.assertRaises(SafeFailure):validate_task(task()|{'destination':'XXX'})
    def test_timeout_becomes_error_and_no_raw_trace(self):
        with patch('subprocess.run',side_effect=subprocess.TimeoutExpired('test',90)):
            self.assertEqual(search_subprocess(task()),{'outcome':'error'})
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
        self.assertEqual(normalize([offer(0),offer(True)],task()),{'outcome':'error'})
    def test_wrong_trip_or_dates_not_saved(self):
        self.assertEqual(normalize([offer(trip_type='one-way'),offer(return_date='2026-11-17')],task()),{'outcome':'error'})
    def test_empty_provider_list_is_empty_not_error_or_free(self):
        self.assertEqual(normalize([],task()),{'outcome':'empty'})
    def test_bad_airline_is_unknown_not_invented(self):
        self.assertIsNone(normalize([offer(primary_airline='bad\nname')],task())['airline'])
    def test_initial_plan_is_small_and_same_dates(self):
        p=plan(date(2026,9,11));self.assertEqual(len(p['tasks']),6);self.assertEqual(p['tasks'][0]['depart_date'],'2026-10-11')
    def test_invalid_plan_duration(self):
        with self.assertRaises(SafeFailure):plan(date(2026,9,11),nights=0)

if __name__=='__main__':unittest.main()
