import test from 'node:test';
import assert from 'node:assert/strict';
import {LocalD1} from '../scripts/sqlite-d1.mjs';
import {createHandler} from '../src/worker.mjs';
import {APP_ID} from '../src/catalog.mjs';
import {DAY,taskSpec} from '../src/logic.mjs';
const ADMIN='a'.repeat(48),COLLECTOR='c'.repeat(48),UUID=()=>crypto.randomUUID();
function rig(t){
  const db=new LocalD1();t.after(()=>db.close());
  const clock={now:Date.parse('2026-09-11T06:00:00Z')};
  const env={DB:db,APP_ID,ADMIN_KEY:ADMIN,COLLECTOR_KEY:COLLECTOR,COLLECTOR_ENABLED:'true',MAX_SEARCHES_PER_HOUR:'3',
    ASSETS:{fetch:async()=>new Response('static asset fixture')}};
  const handler=createHandler(()=>clock.now);
  async function request(path,{method='GET',role,data,raw,headers={}}={}){
    const h=new Headers(headers);
    if(role==='admin')h.set('X-API-Key',ADMIN);if(role==='collector')h.set('Authorization','Bearer '+COLLECTOR);
    if(data!==undefined){method='POST';h.set('Content-Type','application/json');}
    const response=await handler.fetch(new Request('https://radar.example'+path,{method,headers:h,body:raw??(data===undefined?undefined:JSON.stringify(data))}),env);
    let body;try{body=await response.clone().json();}catch{body=await response.clone().text();}
    return {status:response.status,headers:response.headers,body};
  }
  async function seed(tasks=[{origin:'TPE',destination:'FUK',depart_date:'2026-11-12',return_date:'2026-11-16'}]){
    const r=await request('/api/admin/tasks',{role:'admin',data:{tasks}});assert.equal(r.status,202,JSON.stringify(r.body));
    return db.sqlite.prepare('SELECT * FROM cf_radar_tasks ORDER BY id').all();
  }
  async function claim(){const r=await request('/api/collector/claim',{role:'collector',data:{run_id:UUID()}});assert.equal(r.status,200,JSON.stringify(r.body));return r.body.task;}
  async function complete(task,extra={}){return request('/api/collector/result',{role:'collector',data:{
    task_id:task.id,lease_token:task.lease_token,outcome:'ok',price_twd:5980,searched_at:new Date(clock.now).toISOString(),airline:'Synthetic test airline',offer_count:3,...extra}});}
  function snapshot(task,price,at,extra={}){
    const id=UUID(),payload={id,origin:task.origin,destination:task.destination,depart_date:task.depart_date,return_date:task.return_date,
      trip_days:5,price_twd:price,currency:'TWD',adults:1,cabin:'economy',direct_only:true,searched_at:new Date(at).toISOString(),
      airline:null,baseline_confident:false,baseline_twd:null,prior_observed_days:0,drop_pct:null,...extra};
    db.sqlite.prepare(`INSERT INTO cf_radar_snapshots VALUES(?,?,?,?,?,?,?,?,?,?)`).run(id,task.query_key,task.origin,task.destination,
      task.depart_date,task.return_date,5,price,new Date(at).toISOString(),JSON.stringify(payload));return id;
  }
  return {db,clock,env,request,seed,claim,complete,snapshot};
}

test('health verifies database identity and contains no credentials',async t=>{const r=rig(t);const v=await r.request('/api/health');assert.equal(v.status,200);assert.equal(v.body.app_id,APP_ID);assert(!JSON.stringify(v).includes(ADMIN));});
test('wrong database identity is rejected',async t=>{const r=rig(t);r.db.sqlite.exec("UPDATE cf_radar_meta SET value='other-app' WHERE key='app_id'");assert.equal((await r.request('/api/health')).status,503);});
test('missing binding is a clear unavailable state not empty results',async t=>{const r=rig(t);delete r.env.DB;const v=await r.request('/api/ui/quotes');assert.equal(v.status,503);assert(!('quotes'in v.body));});
test('static assets bypass API database checks',async t=>{const r=rig(t);delete r.env.DB;assert.equal((await r.request('/')).body,'static asset fixture');});
test('new database returns no fake fares',async t=>{const r=rig(t);const v=await r.request('/api/ui/quotes');assert.equal(v.status,200);assert.deepEqual(v.body.quotes,[]);assert.equal(v.body.demo,false);});
test('config exposes flags but no admin or collector key',async t=>{const r=rig(t);const v=await r.request('/api/ui/config');assert.equal(v.body.watchlist_scope,'browser_only');assert.equal(v.body.notifications.ntfy,false);assert.equal(v.body.worker.status,'not_started');assert(!JSON.stringify(v.body).includes(COLLECTOR));});
for(const path of ['/api/scan/trigger','/api/admin/tasks','/api/collector/claim','/api/collector/result','/api/collector/report']){
  test(`unauthorized ${path} cannot mutate state`,async t=>{const r=rig(t);const v=await r.request(path,{data:{}});assert.equal(v.status,401);assert.equal(r.db.queries,0);});
}
test('absent admin secret fails closed',async t=>{const r=rig(t);delete r.env.ADMIN_KEY;assert.equal((await r.request('/api/ui/access',{role:'admin'})).status,503);});
test('identical role secrets fail closed',async t=>{const r=rig(t);r.env.COLLECTOR_KEY=ADMIN;assert.equal((await r.request('/api/ui/access',{role:'admin'})).status,503);});
test('collector key does not grant admin access',async t=>{const r=rig(t);assert.equal((await r.request('/api/ui/access',{headers:{'X-API-Key':COLLECTOR}})).status,401);});
test('admin key does not grant collector access',async t=>{const r=rig(t);assert.equal((await r.request('/api/collector/claim',{data:{run_id:UUID()},headers:{Authorization:'Bearer '+ADMIN}})).status,401);});
test('cross-origin writes refused even with correct credential',async t=>{const r=rig(t);assert.equal((await r.request('/api/scan/trigger',{role:'admin',data:{},headers:{Origin:'https://other.example'}})).status,403);});
test('unsupported method returns 405 without permissive CORS',async t=>{const r=rig(t);const v=await r.request('/api/ui/config',{method:'OPTIONS'});assert.equal(v.status,405);assert.equal(v.headers.get('Access-Control-Allow-Origin'),null);});
test('unknown API returns JSON 404, not SPA HTML',async t=>{const r=rig(t);assert.equal((await r.request('/api/nope')).status,404);});
test('JSON content type required',async t=>{const r=rig(t);const v=await r.request('/api/ui/parse',{method:'POST',raw:'{}',headers:{'Content-Type':'text/plain'}});assert.equal(v.status,415);});
test('malformed JSON returns 400',async t=>{const r=rig(t);assert.equal((await r.request('/api/ui/parse',{method:'POST',raw:'{',headers:{'Content-Type':'application/json'}})).status,400);});
test('unknown JSON fields are rejected',async t=>{const r=rig(t);assert.equal((await r.request('/api/ui/parse',{data:{query:'日本',admin:true}})).status,422);});
test('body size limit also applies without Content-Length',async t=>{const r=rig(t);assert.equal((await r.request('/api/ui/parse',{data:{query:'x'.repeat(17000)}})).status,413);});
test('read routes do not enqueue tasks',async t=>{const r=rig(t);await r.request('/api/ui/config');await r.request('/api/ui/quotes');assert.equal(r.db.sqlite.prepare('SELECT COUNT(*) n FROM cf_radar_tasks').get().n,0);});
test('manual enqueue is deduplicated and rate limited',async t=>{const r=rig(t);const data={origin:'TPE',destination:'FUK'};assert.equal((await r.request('/api/scan/trigger',{role:'admin',data})).status,202);assert.equal((await r.request('/api/scan/trigger',{role:'admin',data})).status,429);r.clock.now+=61000;assert.equal((await r.request('/api/scan/trigger',{role:'admin',data})).status,202);assert.equal(r.db.sqlite.prepare('SELECT COUNT(*) n FROM cf_radar_tasks').get().n,1);});
test('manual enqueue does not claim a task or execute a provider',async t=>{const r=rig(t);r.env.COLLECTOR_ENABLED='false';const v=await r.request('/api/scan/trigger',{role:'admin',data:{origin:'TPE',destination:'FUK'}});assert.equal(v.body.collector_enabled,false);assert.equal(r.db.sqlite.prepare('SELECT lease_owner FROM cf_radar_tasks').get().lease_owner,null);});
test('collector is disabled by default and cannot claim',async t=>{const r=rig(t);delete r.env.COLLECTOR_ENABLED;await r.seed();assert.equal((await r.request('/api/collector/claim',{role:'collector',data:{run_id:UUID()}})).status,503);});
test('two claim requests cannot own the same unexpired task',async t=>{const r=rig(t);await r.seed();const first=await r.claim(),second=await r.claim();assert(first);assert.equal(second,null);});
test('expired lease may be reclaimed with a new token',async t=>{const r=rig(t);await r.seed();const a=await r.claim();r.clock.now+=901000;const b=await r.claim();assert.equal(a.id,b.id);assert.notEqual(a.lease_token,b.lease_token);});
test('hourly claim budget cannot be bypassed by another run ID',async t=>{const r=rig(t);await r.seed();await r.claim();await r.claim();await r.claim();const v=await r.request('/api/collector/claim',{role:'collector',data:{run_id:UUID()}});assert.equal(v.status,429);assert(Number(v.headers.get('Retry-After'))>0);});
test('the next hour resets the claim budget',async t=>{const r=rig(t);await r.seed();await r.claim();await r.claim();await r.claim();r.clock.now+=3600000;assert((await r.claim()).id);});
test('success stores one minimum-price observation and matching airline',async t=>{const r=rig(t);await r.seed();const task=await r.claim();const v=await r.complete(task);assert.equal(v.status,200,JSON.stringify(v.body));const q=(await r.request('/api/ui/quotes')).body.quotes;assert.equal(q.length,1);assert.equal(q[0].price_twd,5980);assert.equal(q[0].airline,'Synthetic test airline');assert.equal(q[0].baseline_twd,null);});
test('identical result replay does not duplicate a snapshot or count',async t=>{const r=rig(t);await r.seed();const task=await r.claim();await r.complete(task);const v=await r.complete(task);assert.equal(v.body.replayed,true);assert.equal((await r.request('/api/ui/config')).body.search_snapshots,1);});
test('different result with the same lease is rejected',async t=>{const r=rig(t);await r.seed();const task=await r.claim();await r.complete(task);assert.equal((await r.complete(task,{price_twd:1})).status,409);});
test('lost owner cannot submit a fare',async t=>{const r=rig(t);await r.seed();const task=await r.claim();r.db.sqlite.prepare('UPDATE cf_radar_tasks SET lease_owner=?').run(UUID());assert.equal((await r.complete(task)).status,409);});
test('lease reassign between initial check and transaction prevents stale writes',async t=>{const r=rig(t);await r.seed();const task=await r.claim();r.db.beforeBatch=async()=>{r.db.sqlite.prepare('UPDATE cf_radar_tasks SET lease_owner=?').run(UUID());r.db.beforeBatch=null;};assert.equal((await r.complete(task)).status,409);assert.equal((await r.request('/api/ui/config')).body.search_snapshots,0);});
for(const bad of [0,-1,NaN,Infinity,true,12.5,'6000',1000001]){
  test(`invalid price ${String(bad)} is never a zero/free fare`,async t=>{const r=rig(t);await r.seed();const task=await r.claim();assert.equal((await r.complete(task,{price_twd:bad})).status,422);assert.equal((await r.request('/api/ui/config')).body.search_snapshots,0);});
}
for(const outcome of ['empty','error']){
  test(`${outcome} creates no snapshot, retains last known fare`,async t=>{const r=rig(t);const [dbTask]=await r.seed();r.snapshot(dbTask,8000,r.clock.now-3600000);const task=await r.claim();const v=await r.request('/api/collector/result',{role:'collector',data:{task_id:task.id,lease_token:task.lease_token,outcome}});assert.equal(v.status,200);const q=(await r.request('/api/ui/quotes')).body.quotes;assert.equal(q[0].price_twd,8000);assert.equal((await r.request('/api/ui/config')).body.search_snapshots,1);assert(r.db.sqlite.prepare('SELECT next_run FROM cf_radar_tasks').get().next_run>r.clock.now);});
}
test('non-success cannot smuggle a price',async t=>{const r=rig(t);await r.seed();const task=await r.claim();assert.equal((await r.complete(task,{outcome:'error'})).status,422);});
test('future observation rejected',async t=>{const r=rig(t);await r.seed();const task=await r.claim();assert.equal((await r.complete(task,{searched_at:new Date(r.clock.now+60000).toISOString()})).status,422);});
test('old timestamp outside lease rejected',async t=>{const r=rig(t);await r.seed();const task=await r.claim();assert.equal((await r.complete(task,{searched_at:new Date(r.clock.now-DAY).toISOString()})).status,422);});
test('current batch is excluded from five-day price comparison',async t=>{const r=rig(t);const [dbTask]=await r.seed();for(let d=1;d<=5;d++)r.snapshot(dbTask,8000,r.clock.now-d*DAY);const task=await r.claim();await r.complete(task);const q=(await r.request('/api/ui/quotes')).body.quotes[0];assert.equal(q.baseline_twd,8000);assert.equal(q.prior_observed_days,5);assert.equal(q.drop_pct,25.3);});
test('different travel dates never share history',async t=>{const r=rig(t);const [dbTask]=await r.seed();const other={...dbTask,query_key:'f'.repeat(64),depart_date:'2026-11-13',return_date:'2026-11-17'};for(let d=1;d<=6;d++)r.snapshot(other,50000,r.clock.now-d*DAY);await r.complete(await r.claim());assert.equal((await r.request('/api/ui/quotes')).body.quotes[0].baseline_confident,false);});
test('truncated history refuses a confident discount',async t=>{const r=rig(t);const [dbTask]=await r.seed();for(let i=0;i<721;i++)r.snapshot(dbTask,8000,r.clock.now-(i+1)*60000);await r.complete(await r.claim());assert.equal((await r.request('/api/ui/quotes')).body.quotes[0].history_truncated,true);});
test('newer expensive quote hides older cheap quote for budget filter',async t=>{const r=rig(t);const [task]=await r.seed();r.snapshot(task,5000,r.clock.now-60000);r.snapshot(task,9000,r.clock.now);assert.equal((await r.request('/api/ui/quotes?max_price=6000')).body.quotes.length,0);});
test('expired quote omitted in exploration but retained with stale flag in dates/detail',async t=>{const r=rig(t);const [task]=await r.seed();const id=r.snapshot(task,5000,r.clock.now-7*3600000);assert.equal((await r.request('/api/ui/quotes')).body.quotes.length,0);assert.equal((await r.request('/api/ui/dates/TPE/FUK')).body.quotes[0].expired,true);assert.equal((await r.request('/api/ui/quote/'+id)).body.expired,true);});
test('invalid snapshot UUID yields 422',async t=>{const r=rig(t);assert.equal((await r.request('/api/ui/quote/invalid')).status,422);});
test('unknown valid snapshot UUID yields 404',async t=>{const r=rig(t);assert.equal((await r.request('/api/ui/quote/'+UUID())).status,404);});
for(const query of ['origin=XXX','origin=TPE%27%20OR%201%3D1','start_date=2026-02-30','start_date=2026-12-10&end_date=2026-10-10','min_days=7&max_days=3','limit=101','offset=-1','sort=sql','max_price=0']){
  test(`invalid filter ${query} is rejected`,async t=>{const r=rig(t);assert.equal((await r.request('/api/ui/quotes?'+query)).status,422);});
}
test('source URL is generated by server, with fixed HTTPS origin',async t=>{const r=rig(t);await r.seed();await r.complete(await r.claim());const q=(await r.request('/api/ui/quotes')).body.quotes[0];assert.equal(new URL(q.source_url).origin,'https://www.google.com');assert.equal(q.baggage_verified,false);});
test('seed batch rejects duplicate tasks',async t=>{const r=rig(t);const v={origin:'TPE',destination:'FUK',depart_date:'2026-11-12',return_date:'2026-11-16'};assert.equal((await r.request('/api/admin/tasks',{role:'admin',data:{tasks:[v,v]}})).status,422);});
test('a task capacity failure rolls back all tasks in the seed batch',async t=>{const r=rig(t);for(let i=0;i<127;i++)r.db.sqlite.prepare('INSERT INTO cf_radar_tasks(id,query_key,origin,destination,depart_date,return_date) VALUES(?,?,?,?,?,?)').run(String(i),String(i),'TPE','FUK','2026-11-12','2026-11-16');const v=await r.request('/api/admin/tasks',{role:'admin',data:{tasks:[{origin:'TPE',destination:'KIX',depart_date:'2026-11-12',return_date:'2026-11-16'},{origin:'TPE',destination:'CTS',depart_date:'2026-11-12',return_date:'2026-11-16'}]}});assert.equal(v.status,503);assert.equal(r.db.sqlite.prepare('SELECT COUNT(*) n FROM cf_radar_tasks').get().n,127);});
test('snapshot cap rolls back receipt and leaves task retryable',async t=>{const r=rig(t);await r.seed();const task=await r.claim();r.db.sqlite.exec("UPDATE cf_radar_meta SET value='20000' WHERE key='snapshot_count'");assert.equal((await r.complete(task)).status,503);assert.equal(r.db.sqlite.prepare('SELECT COUNT(*) n FROM cf_radar_receipts').get().n,0);assert.equal(r.db.sqlite.prepare('SELECT lease_owner FROM cf_radar_tasks').get().lease_owner,task.lease_token);});
test('batch with no observations is not advertised as successful ticket collection',async t=>{const r=rig(t);await r.request('/api/collector/report',{role:'collector',data:{run_id:UUID(),attempted:0,observed:0,errors:0}});assert.equal((await r.request('/api/ui/config')).body.worker.status,'batch_empty');});
test('batch status expires without pretending to be a continuous process',async t=>{const r=rig(t);await r.request('/api/collector/report',{role:'collector',data:{run_id:UUID(),attempted:1,observed:1,errors:0}});r.clock.now+=4*3600000;assert.equal((await r.request('/api/ui/config')).body.worker.status,'stale');});
test('public quote list uses two bounded queries, no history N+1',async t=>{const r=rig(t);const [task]=await r.seed();r.snapshot(task,8000,r.clock.now);r.db.queries=0;await r.request('/api/ui/quotes');assert.equal(r.db.queries,2);});

test('schema version mismatch is not advertised as a healthy version one database',async t=>{
  const r=rig(t);r.db.sqlite.exec("UPDATE cf_radar_meta SET value='2' WHERE key='schema_version'");
  assert.equal((await r.request('/api/health')).status,503);
});
