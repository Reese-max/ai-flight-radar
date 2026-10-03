import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {adaptHTML,adaptJS,build} from '../build.mjs';
import {configured} from '../scripts/prepare-config.mjs';
import {ROUTE_KEYS} from '../src/calibration.mjs';
// Minimal explicit fixtures: this is not a claim to have rendered the real UI.
const html=['持續掃描程序','需要有效的程序心跳','觸發一次查價',
 '指定航線，排入一次查價；不是全境掃描，也不會啟動常駐程序。',
 '只有伺服器管理員可透過環境變數設定通知。','/docs/DEPLOYMENT.md',
 '程序心跳只代表程序存在，成功查價必須有新快照。','每一列是不同日期組合的最低觀測價'].join('\n');
const tick=String.fromCharCode(96);
const js=["not_started:'尚未啟動'","stale:'心跳逾期'",'心跳：${relativeTime(cfg.worker.heartbeat_at)}','尚無有效心跳',
 '已提交一個任務；不代表已取得新報價，也未啟動持續掃描。',
 "$('workerHint').textContent=cfg.worker.heartbeat_at?"+tick+'心跳：${relativeTime(cfg.worker.heartbeat_at)}'+tick+":'尚無有效心跳';",
 "$('metricWorker').textContent=workerLabel(cfg.worker.status);$('workerStatus').textContent=workerLabel(cfg.worker.status);"].join('\n');
test('UI adapter changes continuous-process labels to batch labels',()=>{const out=adaptHTML(html);assert(out.includes('定時查價批次'));assert(out.includes('不會立即查價'));assert(!out.includes('持續掃描程序'));});
test('UI adapter shows unavailable calibration and typed batch failures',()=>{const out=adaptJS(js);assert(out.includes("unavailable:'來源不可用'"));assert(out.includes('尚未完成核准的來源校準'));assert(out.includes('收集器未啟用'));assert(out.includes('錯誤類別：'));assert(out.includes('RATE_LIMITED'));});
test('upstream UI marker change fails closed',()=>assert.throws(()=>adaptJS('different UI')));
test('UI copy uses existing assets but never copies secrets',async t=>{const root=await mkdtemp(path.join(tmpdir(),'radar-build-'));t.after(()=>rm(root,{recursive:true,force:true}));await mkdir(path.join(root,'web/assets'),{recursive:true});await writeFile(path.join(root,'web/index.html'),html);await writeFile(path.join(root,'web/assets/app.js'),js);await writeFile(path.join(root,'web/assets/.env'),'MUST_NOT_COPY');await writeFile(path.join(root,'web/assets/tokens.css'),':root{}');const out=await build(root);assert.equal(await readFile(path.join(root,'web/index.html'),'utf8'),html);assert.equal(await readFile(path.join(out,'assets/tokens.css'),'utf8'),':root{}');await assert.rejects(()=>readFile(path.join(out,'assets/.env')));assert((await readFile(path.join(out,'_headers'),'utf8')).includes("frame-ancestors 'none'"));});
const base={name:'ai-flight-radar-cf',d1_databases:[{binding:'DB',database_name:'ai-flight-radar-cf',database_id:'00000000-0000-0000-0000-000000000000'}]};
const metric={attempted:3,successful:3,parse_complete:3,parse_sample_count:3,date_windows:[30,90,180],quote_age_sample_count:3,
  currency_match_count:3,passenger_match_count:3,cabin_match_count:3,directness_match_count:3,safe_link_resolved_count:3,
  search_success_rate:1,parse_completeness_rate:1,quote_age_p95_seconds:90,
  currency_consistency_rate:1,passenger_consistency_rate:1,cabin_consistency_rate:1,directness_consistency_rate:1,
  safe_link_resolution_rate:1,handoff_comparison_count:3,price_discrepancy_p95_percent:1};
function receipt(){const measured=new Date(Date.now()-60000).toISOString();return {schema_version:1,protocol_version:'1.0',provider:'fast_flights',provider_version:'3.1.0',decision:'BUILD',
  measured_at:measured,expires_at:new Date(Date.now()+10*86400000).toISOString(),allowed_routes:ROUTE_KEYS,
  route_metrics:Object.fromEntries(ROUTE_KEYS.map(route=>[route,metric])),blockers:[],
  approvals:{owner_authorized:true,terms_allowed:true,budget_approved:true}};}
test('deployment config refuses placeholder database ID',()=>assert.throws(()=>configured(base,base.d1_databases[0].database_id,'a'.repeat(32))));
test('deployment config refuses an unrelated Worker target',()=>assert.throws(()=>configured({...base,name:'cf-mcp-server'},'12345678-1234-1234-1234-123456789abc','a'.repeat(32))));
test('deployment config changes only target IDs and leaves input unchanged',()=>{const out=configured(base,'12345678-1234-1234-1234-123456789abc','a'.repeat(32));assert.equal(out.name,'ai-flight-radar-cf');assert.equal(base.d1_databases[0].database_id,'00000000-0000-0000-0000-000000000000');});
test('deployment config refuses collector enablement without a current passing receipt',()=>{
  assert.throws(()=>configured(base,'12345678-1234-1234-1234-123456789abc','a'.repeat(32),'true'));
});
test('deployment config embeds the checked receipt beside the enable flag',()=>{
  const out=configured(base,'12345678-1234-1234-1234-123456789abc','a'.repeat(32),'true',3,receipt());
  assert.equal(out.vars.COLLECTOR_ENABLED,'true');assert.equal(JSON.parse(out.vars.CALIBRATION_ADMISSION).decision,'BUILD');
});
