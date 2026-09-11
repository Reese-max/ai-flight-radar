import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,readFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {adaptHTML,adaptJS,build} from '../build.mjs';
import {configured} from '../scripts/prepare-config.mjs';
// Minimal explicit fixtures: this is not a claim to have rendered the real UI.
const html=['持續掃描程序','需要有效的程序心跳','觸發一次查價',
 '指定航線，排入一次查價；不是全境掃描，也不會啟動常駐程序。',
 '只有伺服器管理員可透過環境變數設定通知。','/docs/DEPLOYMENT.md',
 '程序心跳只代表程序存在，成功查價必須有新快照。','每一列是不同日期組合的最低觀測價'].join('\n');
const js=["not_started:'尚未啟動'","stale:'心跳逾期'",'心跳：${relativeTime(cfg.worker.heartbeat_at)}','尚無有效心跳',
 '已提交一個任務；不代表已取得新報價，也未啟動持續掃描。',"$('metricWorker').textContent=workerLabel(cfg.worker.status);"].join('\n');
test('UI adapter changes continuous-process labels to batch labels',()=>{const out=adaptHTML(html);assert(out.includes('定時查價批次'));assert(out.includes('不會立即查價'));assert(!out.includes('持續掃描程序'));});
test('UI adapter shows disabled collector explicitly',()=>assert(adaptJS(js).includes("'收集器關閉'")));
test('upstream UI marker change fails closed',()=>assert.throws(()=>adaptJS('different UI')));
test('UI copy uses existing assets but never copies secrets',async t=>{const root=await mkdtemp(path.join(tmpdir(),'radar-build-'));t.after(()=>rm(root,{recursive:true,force:true}));await mkdir(path.join(root,'web/assets'),{recursive:true});await writeFile(path.join(root,'web/index.html'),html);await writeFile(path.join(root,'web/assets/app.js'),js);await writeFile(path.join(root,'web/assets/.env'),'MUST_NOT_COPY');await writeFile(path.join(root,'web/assets/tokens.css'),':root{}');const out=await build(root);assert.equal(await readFile(path.join(root,'web/index.html'),'utf8'),html);assert.equal(await readFile(path.join(out,'assets/tokens.css'),'utf8'),':root{}');await assert.rejects(()=>readFile(path.join(out,'assets/.env')));assert((await readFile(path.join(out,'_headers'),'utf8')).includes("frame-ancestors 'none'"));});
const base={name:'ai-flight-radar-cf',d1_databases:[{binding:'DB',database_name:'ai-flight-radar-cf',database_id:'00000000-0000-0000-0000-000000000000'}]};
test('deployment config refuses placeholder database ID',()=>assert.throws(()=>configured(base,base.d1_databases[0].database_id,'a'.repeat(32))));
test('deployment config refuses an unrelated Worker target',()=>assert.throws(()=>configured({...base,name:'cf-mcp-server'},'12345678-1234-1234-1234-123456789abc','a'.repeat(32))));
test('deployment config changes only target IDs and leaves input unchanged',()=>{const out=configured(base,'12345678-1234-1234-1234-123456789abc','a'.repeat(32));assert.equal(out.name,'ai-flight-radar-cf');assert.equal(base.d1_databases[0].database_id,'00000000-0000-0000-0000-000000000000');});
