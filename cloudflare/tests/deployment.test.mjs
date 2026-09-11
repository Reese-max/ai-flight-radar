import test from 'node:test';
import assert from 'node:assert/strict';
import {inspectSettings} from '../scripts/deployment-preflight.mjs';
const good={CLOUDFLARE_API_TOKEN:'synthetic-test-only',CLOUDFLARE_ACCOUNT_ID:'a'.repeat(32),CF_RADAR_DATABASE_ID:'12345678-1234-1234-1234-123456789abc',CF_RADAR_ADMIN_KEY:'a'.repeat(48),CF_RADAR_COLLECTOR_KEY:'b'.repeat(48)};
test('preflight reports setting names without credential values',()=>{const r=inspectSettings(good);assert.equal(r.ready,true);assert(!JSON.stringify(r).includes(good.CF_RADAR_ADMIN_KEY));});
test('preflight refuses all missing settings',()=>{const r=inspectSettings({});assert.equal(r.ready,false);assert.equal(r.missing.length,5);});
test('preflight rejects placeholder database',()=>assert.equal(inspectSettings({...good,CF_RADAR_DATABASE_ID:'00000000-0000-0000-0000-000000000000'}).ready,false));
test('preflight rejects reused role secrets',()=>assert.equal(inspectSettings({...good,CF_RADAR_COLLECTOR_KEY:good.CF_RADAR_ADMIN_KEY}).ready,false));
test('preflight rejects weak role key and malformed account',()=>assert.equal(inspectSettings({...good,CF_RADAR_ADMIN_KEY:'short',CLOUDFLARE_ACCOUNT_ID:'x'}).ready,false));
