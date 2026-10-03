import test from 'node:test';
import assert from 'node:assert/strict';
import {DATE_WINDOWS,evaluateCalibration,inspectAdmission,OUTCOMES,ROUTE_KEYS,validateObservation} from '../src/calibration.mjs';

const now='2026-09-11T08:00:00.000Z';
const profile={trip_type:'round_trip',adults:1,cabin:'economy',direct_only:true};
const dates={30:'2026-10-11',90:'2026-12-10',180:'2027-03-10'};
function success(route,extra={}){
  return {outcome:'SUCCESS',route,queried_at:'2026-09-11T06:00:00.000Z',depart_date:dates[30],profile,parse_complete:true,
    quote_age_seconds:90,observed_currency:'TWD',observed_adults:1,observed_cabin:'economy',observed_direct_only:true,
    link_resolution:'resolved_safe',displayed_price_twd:6000,handoff_price_twd:6060,
    handoff_checked_at:'2026-09-11T06:10:00.000Z',...extra};
}
function allRouteSamples(){
  return ROUTE_KEYS.flatMap(route=>DATE_WINDOWS.map(days=>success(route,{depart_date:dates[days]})));
}
function evaluated(observations,overrides={}){
  return evaluateCalibration(observations,{authorized:true,terms_allowed:true,budget_approved:true,evaluated_at:now,...overrides});
}

test('typed observation contract covers every declared outcome',()=>{
  const common={route:'TPE/FUK',queried_at:now,depart_date:'2026-10-11',profile};
  const fixtures=[
    success('TPE/FUK'),
    {...common,outcome:'NO_RESULTS'},
    {...common,outcome:'RATE_LIMITED',reason_code:'provider_rate_limit'},
    {...common,outcome:'UPSTREAM_CHANGED',reason_code:'schema_change'},
    {...common,outcome:'PARSE_FAILED',reason_code:'partial_payload'},
    {...common,outcome:'BLOCKED',reason_code:'unsupported_profile',profile:{...profile,adults:2}},
  ];
  assert.deepEqual(fixtures.map(x=>x.outcome),OUTCOMES);
  for(const item of fixtures)assert.equal(validateObservation(item),true,item.outcome);
});

test('NO_RESULTS is an attempt, never a successful quote',()=>{
  const samples=DATE_WINDOWS.map(days=>({outcome:'NO_RESULTS',route:'TPE/FUK',queried_at:'2026-09-11T06:00:00.000Z',
    depart_date:dates[days],profile}));
  const receipt=evaluated(samples);
  assert.equal(receipt.decision,'BLOCK');
  assert.equal(receipt.route_metrics['TPE/FUK'].attempted,3);
  assert.equal(receipt.route_metrics['TPE/FUK'].successful,0);
  assert.equal(receipt.route_metrics['TPE/FUK'].search_success_rate,0);
});

test('a complete passing synthetic matrix produces BUILD for all configured routes',()=>{
  const receipt=evaluated(allRouteSamples());
  assert.equal(receipt.decision,'BUILD');
  assert.deepEqual(receipt.allowed_routes,ROUTE_KEYS);
  assert.equal(inspectAdmission(receipt,Date.parse(now)).admitted,true);
});

test('only routes meeting every threshold enter a NARROW decision',()=>{
  const samples=allRouteSamples();
  samples[0]=success(ROUTE_KEYS[0],{observed_currency:'USD'});
  const receipt=evaluated(samples);
  assert.equal(receipt.decision,'NARROW');
  assert(!receipt.allowed_routes.includes(ROUTE_KEYS[0]));
  assert.equal(inspectAdmission(receipt,Date.parse(now)).admitted,true);
});

test('missing owner approvals or a hard stop keeps the decision BLOCK',()=>{
  const samples=[...Array.from({length:3},()=>success('TPE/FUK')),
    {outcome:'RATE_LIMITED',route:'TPE/FUK',queried_at:now,profile,reason_code:'provider_rate_limit'}];
  assert.equal(evaluateCalibration(allRouteSamples(),{terms_allowed:true,budget_approved:true,evaluated_at:now}).decision,'BLOCK');
  assert.equal(evaluated(samples).decision,'BLOCK');
  for(const outcome of ['UPSTREAM_CHANGED','PARSE_FAILED','BLOCKED']){
    const reason_code={UPSTREAM_CHANGED:'schema_change',PARSE_FAILED:'partial_payload',BLOCKED:'owner_stop'}[outcome];
    assert.equal(evaluated([{outcome,route:'TPE/FUK',queried_at:now,profile,reason_code}]).decision,'BLOCK');
  }
});

test('unsafe links and mismatched profiles can never admit a route',()=>{
  const samples=allRouteSamples();
  samples[0]=success(ROUTE_KEYS[0],{link_resolution:'unsafe',handoff_price_twd:null,handoff_checked_at:null});
  assert.equal(evaluated(samples).decision,'BLOCK');
  const unsupported=success('TPE/FUK',{profile:{...profile,adults:2}});
  assert.equal(validateObservation(unsupported),false);
  assert.equal(validateObservation({outcome:'NO_RESULTS',route:'TPE/FUK',queried_at:now,
    profile:{...profile,trip_type:'one_way'}}),false);
});

test('malformed, partial, or raw-payload observations are rejected before replay',()=>{
  assert.equal(validateObservation(success('TPE/FUK',{parse_complete:false})),false);
  assert.equal(validateObservation(success('TPE/FUK',{booking_url:'https://example.test'})),false);
  assert.equal(validateObservation(success('TPE/FUK',{provider_html:'raw response'})),false);
  assert.equal(validateObservation(success('TPE/FUK',{quote_age_seconds:null})),true);
  assert.equal(evaluated(ROUTE_KEYS.slice(0,1).flatMap(route=>DATE_WINDOWS.map(days=>success(route,{depart_date:dates[days],quote_age_seconds:null}))).concat(
    ...ROUTE_KEYS.slice(1).flatMap(route=>DATE_WINDOWS.map(days=>success(route,{depart_date:dates[days]}))))).decision,'NARROW');
});

test('route admission requires unique 30, 90, and 180 day strata within the 48-search budget',()=>{
  const samples=allRouteSamples();
  samples[1]={...samples[1],depart_date:dates[30]};
  assert.equal(evaluated(samples).blockers[0],'sample_budget_exceeded');
  assert.equal(evaluated([...allRouteSamples(),success('TPE/FUK')]).decision,'BLOCK');
  assert.equal(validateObservation(success('TPE/FUK',{depart_date:'2026-10-12'})),false);
});

test('receipt validity is time-bounded and binds provider, version, thresholds, and route set',()=>{
  const receipt=evaluated(allRouteSamples());
  assert.equal(inspectAdmission(receipt,Date.parse('2026-09-26T08:00:00.000Z')).state,'expired');
  assert.equal(inspectAdmission({...receipt,provider_version:'3.2.0'},Date.parse(now)).state,'invalid');
  assert.equal(inspectAdmission({...receipt,allowed_routes:['TPE/XXX']},Date.parse(now)).state,'invalid');
  assert.equal(inspectAdmission({...receipt,route_metrics:{...receipt.route_metrics,'TPE/FUK':{...receipt.route_metrics['TPE/FUK'],price_discrepancy_p95_percent:20}}},Date.parse(now)).state,'invalid');
  assert.equal(inspectAdmission({...receipt,blockers:['owner_stop']},Date.parse(now)).state,'invalid');
  assert.equal(inspectAdmission({...receipt,approvals:{...receipt.approvals,budget_approved:false}},Date.parse(now)).state,'invalid');
  assert.equal(inspectAdmission({...receipt,raw_provider_response:'must never be retained'},Date.parse(now)).state,'invalid');
});
