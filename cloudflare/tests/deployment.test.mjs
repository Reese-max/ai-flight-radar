import test from 'node:test';
import assert from 'node:assert/strict';
import {inspectSettings} from '../scripts/deployment-preflight.mjs';
import {ROUTE_KEYS} from '../src/calibration.mjs';
const good={CLOUDFLARE_API_TOKEN:'synthetic-test-only',CLOUDFLARE_ACCOUNT_ID:'a'.repeat(32),CF_RADAR_DATABASE_ID:'12345678-1234-1234-1234-123456789abc',CF_RADAR_ADMIN_KEY:'a'.repeat(48),CF_RADAR_COLLECTOR_KEY:'b'.repeat(48)};
const metric={attempted:3,successful:3,parse_complete:3,parse_sample_count:3,date_windows:[30,90,180],quote_age_sample_count:3,
  currency_match_count:3,passenger_match_count:3,cabin_match_count:3,directness_match_count:3,safe_link_resolved_count:3,
  search_success_rate:1,parse_completeness_rate:1,quote_age_p95_seconds:90,
  currency_consistency_rate:1,passenger_consistency_rate:1,cabin_consistency_rate:1,directness_consistency_rate:1,
  safe_link_resolution_rate:1,handoff_comparison_count:3,price_discrepancy_p95_percent:1};
const measuredAt=new Date(Date.now()-60000).toISOString();
const buildReceipt={schema_version:1,protocol_version:'1.0',provider:'fast_flights',provider_version:'3.1.0',decision:'BUILD',
  measured_at:measuredAt,expires_at:new Date(Date.now()+10*86400000).toISOString(),allowed_routes:ROUTE_KEYS,
  route_metrics:Object.fromEntries(ROUTE_KEYS.map(route=>[route,metric])),blockers:[],
  approvals:{owner_authorized:true,terms_allowed:true,budget_approved:true}};
test('preflight reports setting names without credential values',()=>{const r=inspectSettings(good);assert.equal(r.ready,true);assert(!JSON.stringify(r).includes(good.CF_RADAR_ADMIN_KEY));});
test('preflight refuses all missing settings',()=>{const r=inspectSettings({});assert.equal(r.ready,false);assert.equal(r.missing.length,5);});
test('preflight rejects placeholder database',()=>assert.equal(inspectSettings({...good,CF_RADAR_DATABASE_ID:'00000000-0000-0000-0000-000000000000'}).ready,false));
test('preflight rejects reused role secrets',()=>assert.equal(inspectSettings({...good,CF_RADAR_COLLECTOR_KEY:good.CF_RADAR_ADMIN_KEY}).ready,false));
test('preflight rejects weak role key and malformed account',()=>assert.equal(inspectSettings({...good,CF_RADAR_ADMIN_KEY:'short',CLOUDFLARE_ACCOUNT_ID:'x'}).ready,false));
test('preflight refuses collector enablement without a current passing receipt',()=>{
  assert.equal(inspectSettings({...good,CF_RADAR_COLLECTOR_ENABLED:'true'}).invalid.includes('CF_RADAR_COLLECTOR_ENABLED_CALIBRATION'),true);
  assert.equal(inspectSettings({...good,CF_RADAR_COLLECTOR_ENABLED:'true'},{...buildReceipt,decision:'BLOCK',allowed_routes:[],blockers:['owner_stop']}).ready,false);
});
test('preflight accepts a current complete BUILD receipt for explicit collector enablement',()=>{
  assert.equal(inspectSettings({...good,CF_RADAR_COLLECTOR_ENABLED:'true'},buildReceipt).ready,true);
});
test('preflight refuses scheduled task seeding while collector is disabled',()=>{
  assert.equal(inspectSettings({...good,CF_RADAR_SEED_ENABLED:'true'}).invalid.includes('CF_RADAR_SEED_ENABLED_REQUIRES_COLLECTOR'),true);
});
