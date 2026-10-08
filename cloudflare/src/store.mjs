import {APP_ID,origins,destinations,routes} from './catalog.mjs';
import {collectorAdmission,inspectAdmission,ERROR_TYPES} from './calibration.mjs';
import {DAY,REVISIT_MS,ERROR_BACKOFF_MS,TTL,HttpError,requireThat,record,integer,text,timestamp,dateOnly,taipeiToday,addDays,codes,taskSpec,digest,summarize,quoteView} from './logic.mjs';
const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const keyPattern=/^[0-9a-f]{64}$/;
export async function ready(env){
  requireThat(env.APP_ID===APP_ID&&env.DB,'Deployment is not configured',503);
  const {results}=await env.DB.prepare("SELECT key,value FROM cf_radar_meta WHERE key IN ('app_id','schema_version')").all();
  const identity=Object.fromEntries(results.map(row=>[row.key,row.value]));
  requireThat(identity.app_id===APP_ID&&identity.schema_version==='1','Database identity/schema mismatch',503);
}
export async function budget(db,name,limit,period,now){
  const start=Math.floor(now/period)*period;
  const row=await db.prepare(`INSERT INTO cf_radar_budgets(name,window_start,used) VALUES(?,?,1)
    ON CONFLICT(name) DO UPDATE SET window_start=excluded.window_start,
      used=CASE WHEN cf_radar_budgets.window_start=excluded.window_start THEN cf_radar_budgets.used+1 ELSE 1 END
    WHERE cf_radar_budgets.window_start<>excluded.window_start OR cf_radar_budgets.used<? RETURNING used`)
    .bind(name,start,limit).first();
  if(!row)throw new HttpError(429,'Operation budget exhausted',{'Retry-After':String(Math.ceil((start+period-now)/1000))});
}
function paramInt(params,name,fallback,min,max){
  const value=params.get(name);if(value===null)return fallback;
  requireThat(/^\d+$/.test(value),`Invalid ${name}`);return integer(Number(value),min,max,name);
}
export async function quotes(db,params,now){
  const start=params.get('start_date')||taipeiToday(now),end=params.get('end_date')||addDays(start,180);
  dateOnly(start);dateOnly(end);
  requireThat(end>start&&(Date.parse(end)-Date.parse(start))/DAY<=366,'Invalid date range');
  const min=paramInt(params,'min_days',2,2,31),max=paramInt(params,'max_days',31,2,31);
  requireThat(min<=max,'Invalid duration range');
  const limit=paramInt(params,'limit',48,1,100),offset=paramInt(params,'offset',0,0,5000);
  const sort=params.get('sort')||'price';requireThat(['price','recent'].includes(sort),'Invalid sorting');
  const cond=['l.depart_date>=?','l.return_date<=?','l.trip_days>=?','l.trip_days<=?',
    'l.searched_at>=?','l.searched_at<=?','l.depart_date>=?'];
  const args=[start,end,min,max,new Date(now-TTL).toISOString(),new Date(now).toISOString(),taipeiToday(now)];
  for(const [field,list] of [['origin',origins],['destination',destinations]]){
    const selected=codes(params.get(field),list);
    if(selected.length){cond.push(`l.${field} IN (${selected.map(()=>'?').join(',')})`);args.push(...selected);}
  }
  if(params.has('max_price')){cond.push('l.price_twd<=?');args.push(paramInt(params,'max_price',null,1,1000000));}
  const order=sort==='recent'?'l.searched_at DESC,l.snapshot_id':'l.price_twd,l.snapshot_id';
  const {results}=await db.prepare(`SELECT s.payload FROM cf_radar_latest l
    JOIN cf_radar_snapshots s ON s.id=l.snapshot_id WHERE ${cond.join(' AND ')}
    ORDER BY ${order} LIMIT ? OFFSET ?`).bind(...args,limit+1,offset).all();
  return {quotes:results.slice(0,limit).map(r=>quoteView(JSON.parse(r.payload),now)),
    next_offset:results.length>limit?offset+limit:null,generated_at:new Date(now).toISOString(),demo:false,
    note:'Observed quotes only; baggage, complete itinerary and final availability require confirmation.'};
}
export async function detail(db,id,now){
  requireThat(uuid.test(id),'Invalid quote ID');
  const row=await db.prepare('SELECT payload FROM cf_radar_snapshots WHERE id=?').bind(id).first();
  requireThat(row,'Quote not found',404);return quoteView(JSON.parse(row.payload),now);
}
export async function dates(db,origin,destination,now){
  const os=codes(origin,origins),ds=codes(destination,destinations);
  requireThat(os.length===1&&ds.length===1,'One route required');
  const {results}=await db.prepare(`SELECT s.payload FROM cf_radar_latest l
    JOIN cf_radar_snapshots s ON s.id=l.snapshot_id
    WHERE l.origin=? AND l.destination=? AND l.depart_date>=? AND l.return_date<=?
    ORDER BY l.depart_date,l.return_date,l.snapshot_id LIMIT 181`)
    .bind(os[0],ds[0],taipeiToday(now),addDays(taipeiToday(now),366)).all();
  return {quotes:results.slice(0,180).map(r=>quoteView(JSON.parse(r.payload),now)),truncated:results.length>180,
    note:'Latest observation per travel-date combination, not an observation-time trend.'};
}
export async function config(env,now){
  const {results}=await env.DB.prepare(`SELECT key,value FROM cf_radar_meta
    WHERE key IN ('snapshot_count','last_quote_at','last_batch')`).all();
  const meta=Object.fromEntries(results.map(x=>[x.key,x.value]));
  const run=meta.last_batch?JSON.parse(meta.last_batch):null;
  const errorTypes={};
  if(run?.error_types&&typeof run.error_types==='object'&&!Array.isArray(run.error_types))
    for(const [type,count] of Object.entries(run.error_types))
      if(ERROR_TYPES.includes(type)&&Number.isSafeInteger(count)&&count>=0&&count<=10)errorTypes[type]=count;
  const batchAt=run?Date.parse(run.at):NaN;
  const age=run?now-batchAt:Infinity;
  const status=!run?'not_started':!Number.isFinite(batchAt)||age>3*3600000||age<0?'stale':
    run.errors>0?'batch_error':run.observed>0?'batch_ok':'batch_empty';
  const admission=inspectAdmission(env.CALIBRATION_ADMISSION,now);
  const admitted=env.COLLECTOR_ENABLED==='true'&&admission.admitted;
  let sourceHealth;
  if(!admitted)sourceHealth={state:'unavailable',reason:admission.state==='expired'?'calibration_expired':
    admission.state==='invalid'?'calibration_invalid':admission.state==='blocked'?'calibration_blocked':'collector_disabled'};
  else if(!run)sourceHealth={state:'unavailable',reason:'batch_not_started'};
  else if(!Number.isFinite(batchAt)||age>3*3600000||age<0)sourceHealth={state:'stale',reason:'batch_stale'};
  else if(run.errors>0&&run.observed>0)sourceHealth={state:'partial',reason:'batch_partial'};
  else if(run.errors>0||run.observed===0)sourceHealth={state:'unavailable',reason:run.errors>0?'batch_failed':'no_successful_observation'};
  else sourceHealth={state:'available',reason:'recent_successful_batch'};
  return {ui_version:'2.0-cf',public_mode:true,manual_scan_requires_key:true,
    origins,destinations,routes,search_snapshots:Number(meta.snapshot_count||0),last_quote_at:meta.last_quote_at||null,
    worker:{status,heartbeat_at:run?.at||null,kind:'scheduled_batch',collector_enabled:admitted,
      collector_requested_enabled:env.COLLECTOR_ENABLED==='true',
      error_types:errorTypes,
      calibration:{state:admission.state,decision:admission.decision,reason:admission.reason,
        measured_at:admission.measured_at,expires_at:admission.expires_at,allowed_routes:admission.allowed_routes},
      source_health:sourceHealth},
    notifications:{ntfy:false,telegram:false},watchlist_scope:'browser_only',source_count:1};
}
function insertTask(db,t){
  return db.prepare(`INSERT INTO cf_radar_tasks(id,query_key,origin,destination,depart_date,return_date) VALUES(?,?,?,?,?,?)
    ON CONFLICT(query_key) DO UPDATE SET next_run=0,enabled=1`)
    .bind(t.id,t.query_key,t.origin,t.destination,t.depart_date,t.return_date);
}
export async function seed(env,body,now){
  const db=env.DB;
  const admission=collectorAdmission(env,now);
  requireThat(admission.admitted,'Task seeding is not admitted by current calibration',503);
  record(body,['tasks']);requireThat(Array.isArray(body.tasks)&&body.tasks.length>=1&&body.tasks.length<=24,'Provide 1-24 tasks');
  const tasks=await Promise.all(body.tasks.map(x=>taskSpec(x,now)));
  requireThat(tasks.every(task=>admission.allowed_routes.includes(task.origin+'/'+task.destination)),
    'A task is outside the calibrated route scope');
  requireThat(new Set(tasks.map(x=>x.id)).size===tasks.length,'Duplicate tasks');
  await budget(db,'admin_seed',1,60000,now);
  await db.batch(tasks.map(t=>insertTask(db,t)));return {queued:tasks.length};
}
export async function enqueue(env,body,now){
  record(body,['origin','destination']);
  const os=codes(body.origin,origins),ds=codes(body.destination,destinations);
  requireThat(os.length===1&&ds.length===1,'One origin/destination required');
  const route=os[0]+'/'+ds[0];
  requireThat(routes.some(item=>item.origin+'/'+item.destination===route),'Route is outside the configured collection scope');
  const admission=collectorAdmission(env,now);
  if(admission.admitted)requireThat(admission.allowed_routes.includes(route),'Route is outside the calibrated collection scope');
  const existing=await env.DB.prepare(`SELECT depart_date,return_date FROM cf_radar_tasks
    WHERE origin=? AND destination=? AND depart_date>=? ORDER BY next_run,id LIMIT 1`)
    .bind(os[0],ds[0],taipeiToday(now)).first();
  const task=await taskSpec({...body,depart_date:existing?.depart_date||addDays(taipeiToday(now),30),
    return_date:existing?.return_date||addDays(taipeiToday(now),34)},now);
  await budget(env.DB,'manual_queue',1,60000,now);
  await insertTask(env.DB,task).run();
  return {status:'queued',task_id:task.id,collector_enabled:admission.admitted,
    message:'加入待查清單，等待另行啟用的批次。沒有立即查價。'};
}
export async function claim(env,body,now){
  record(body,['run_id']);requireThat(uuid.test(body.run_id),'Invalid run ID');
  const admission=collectorAdmission(env,now);
  requireThat(admission.admitted,'Collector is not admitted by current calibration',503);
  const limit=Number(env.MAX_SEARCHES_PER_HOUR??'');integer(limit,1,10,'server claim budget');
  await budget(env.DB,'collector_claim',limit,3600000,now);
  const token=crypto.randomUUID();
  const routeFilter=' AND ('+admission.allowed_routes.map(()=>'(origin=? AND destination=?)').join(' OR ')+')';
  const routeValues=admission.allowed_routes.flatMap(route=>route.split('/'));
  const sql='UPDATE cf_radar_tasks SET lease_owner=?,lease_until=? WHERE id=(SELECT id FROM cf_radar_tasks WHERE enabled=1 AND depart_date>=? AND next_run<=? AND lease_until<=?'+routeFilter+' ORDER BY next_run,id LIMIT 1) AND lease_until<=? RETURNING id,origin,destination,depart_date,return_date,lease_owner,lease_until';
  const task=await env.DB.prepare(sql).bind(token,now+900000,taipeiToday(now),now,now,...routeValues,now).first();
  return {task:task?{...task,lease_token:task.lease_owner,lease_owner:undefined}:null,
    scope:{source:'google_flights',currency:'TWD',adults:1,cabin:'economy',direct_only:true}};
}
function normalizeResult(body){
  record(body,['task_id','lease_token','outcome','price_twd','searched_at','airline','offer_count','error_type']);
  requireThat(keyPattern.test(body.task_id)&&uuid.test(body.lease_token),'Invalid task or lease');
  requireThat(['ok','empty','error'].includes(body.outcome),'Invalid result outcome');
  const clean={task_id:body.task_id,lease_token:body.lease_token,outcome:body.outcome};
  if(body.outcome==='ok'){
    clean.price_twd=integer(body.price_twd,1,1000000,'price');clean.searched_at=timestamp(body.searched_at);
    clean.airline=body.airline===null?null:text(body.airline,120,'airline');
    clean.offer_count=integer(body.offer_count,1,1000,'offer count');
  }else requireThat(['price_twd','searched_at','airline','offer_count'].every(k=>!(k in body)),'Non-success must not include a fare');
  if(body.outcome==='error'){
    if('error_type' in body){
      clean.error_type=body.error_type;
      requireThat(ERROR_TYPES.includes(clean.error_type),'Invalid error type');
    }
  }else requireThat(!('error_type' in body),'Only errors may include an error type');
  return clean;
}
export async function complete(env,body,now){
  const admission=collectorAdmission(env,now);
  requireThat(admission.admitted,'Collector is not admitted by current calibration',503);
  const clean=normalizeResult(body),hash=await digest(JSON.stringify(clean));
  const prior=await env.DB.prepare('SELECT payload_hash FROM cf_radar_receipts WHERE token=?').bind(clean.lease_token).first();
  if(prior){requireThat(prior.payload_hash===hash,'Different payload for same lease',409);return {status:'accepted',replayed:true,observed:clean.outcome==='ok'};}
  const task=await env.DB.prepare('SELECT * FROM cf_radar_tasks WHERE id=?').bind(clean.task_id).first();
  requireThat(task&&task.lease_owner===clean.lease_token&&task.lease_until>now,'Lease expired or not owned',409);
  requireThat(admission.allowed_routes.includes(task.origin+'/'+task.destination),'Task is outside the calibrated route scope',503);
  let payload;
  if(clean.outcome==='ok'){
    const at=Date.parse(clean.searched_at);
    requireThat(at<=now&&at>=task.lease_until-960000,'Observation timestamp outside this lease');
    const {results}=await env.DB.prepare(`SELECT searched_at,price_twd FROM cf_radar_snapshots
      WHERE query_key=? AND searched_at<? AND searched_at>=? ORDER BY searched_at DESC LIMIT 721`)
      .bind(task.query_key,clean.searched_at,new Date(at-30*DAY).toISOString()).all();
    const stats=summarize(results.slice(0,720),clean.searched_at),truncated=results.length>720;
    if(truncated){stats.baseline_confident=false;stats.baseline_twd=null;}
    const source=new URL('https://www.google.com/travel/flights');
    source.searchParams.set('q',`Flights from ${task.origin} to ${task.destination} on ${task.depart_date} returning ${task.return_date} nonstop`);
    source.searchParams.set('curr','TWD');
    payload={id:clean.lease_token,origin:task.origin,destination:task.destination,depart_date:task.depart_date,return_date:task.return_date,
      trip_days:(Date.parse(task.return_date)-Date.parse(task.depart_date))/DAY+1,price_twd:clean.price_twd,
      currency:'TWD',adults:1,cabin:'economy',direct_only:true,airline:clean.airline,searched_at:clean.searched_at,
      ...stats,history_truncated:truncated,drop_pct:stats.baseline_confident?
        Math.round((stats.baseline_twd-clean.price_twd)/stats.baseline_twd*1000)/10:null,
      source:'Google Flights',baggage_verified:false,source_url:source.href,offer_count:clean.offer_count};
  }
  const taskOutcome=clean.outcome==='error'?'error:'+(clean.error_type??'UNKNOWN'):clean.outcome;
  const statements=[env.DB.prepare(`INSERT INTO cf_radar_receipts(token,payload_hash,task_id,outcome,completed_at)
    SELECT ?,?,?,?,? WHERE EXISTS(SELECT 1 FROM cf_radar_tasks WHERE id=? AND lease_owner=? AND lease_until>?)
    ON CONFLICT(token) DO NOTHING`).bind(clean.lease_token,hash,task.id,clean.outcome,new Date(now).toISOString(),task.id,clean.lease_token,now)];
  if(payload)statements.push(env.DB.prepare(`INSERT INTO cf_radar_snapshots
      (id,query_key,origin,destination,depart_date,return_date,trip_days,price_twd,searched_at,payload)
      SELECT ?,?,?,?,?,?,?,?,?,? WHERE EXISTS(SELECT 1 FROM cf_radar_receipts WHERE token=? AND payload_hash=?)
      ON CONFLICT(id) DO NOTHING`).bind(payload.id,task.query_key,payload.origin,payload.destination,payload.depart_date,
      payload.return_date,payload.trip_days,payload.price_twd,payload.searched_at,JSON.stringify(payload),clean.lease_token,hash));
  statements.push(env.DB.prepare(`UPDATE cf_radar_tasks SET lease_owner=NULL,lease_until=0,next_run=?,last_outcome=?
    WHERE id=? AND lease_owner=? AND EXISTS(SELECT 1 FROM cf_radar_receipts WHERE token=? AND payload_hash=?)`)
    .bind(now+(clean.outcome==='error'?ERROR_BACKOFF_MS:REVISIT_MS),taskOutcome,task.id,clean.lease_token,clean.lease_token,hash));
  const result=await env.DB.batch(statements);
  const receipt=await env.DB.prepare('SELECT payload_hash FROM cf_radar_receipts WHERE token=?').bind(clean.lease_token).first();
  requireThat(receipt?.payload_hash===hash,'Lease was reassigned or payload conflicted',409);
  return {status:'accepted',replayed:result[0].meta.changes===0,observed:clean.outcome==='ok'};
}
export async function report(env,body,now){
  requireThat(collectorAdmission(env,now).admitted,'Collector is not admitted by current calibration',503);
  record(body,['run_id','attempted','observed','errors','error_types']);requireThat(uuid.test(body.run_id),'Invalid run ID');
  integer(body.attempted,0,10);integer(body.observed,0,body.attempted);integer(body.errors,0,body.attempted);
  requireThat(body.observed+body.errors<=body.attempted,'Invalid batch counts');
  const errorTypes={};
  if(body.error_types!==undefined){
    requireThat(body.error_types&&typeof body.error_types==='object'&&!Array.isArray(body.error_types),'Invalid error type counts');
    for(const [type,count] of Object.entries(body.error_types)){
      requireThat(ERROR_TYPES.includes(type),'Invalid error type');
      errorTypes[type]=integer(count,0,body.errors,'error type count');
    }
  }
  const typedErrors=Object.values(errorTypes).reduce((sum,count)=>sum+count,0);
  requireThat(typedErrors<=body.errors,'Error type counts exceed error total');
  if(typedErrors<body.errors)errorTypes.UNKNOWN=(errorTypes.UNKNOWN||0)+body.errors-typedErrors;
  await budget(env.DB,'collector_report',12,3600000,now);
  await env.DB.prepare(`INSERT INTO cf_radar_meta(key,value) VALUES('last_batch',?)
    ON CONFLICT(key) DO UPDATE SET value=excluded.value`)
    .bind(JSON.stringify({run_id:body.run_id,attempted:body.attempted,observed:body.observed,errors:body.errors,
      error_types:errorTypes,at:new Date(now).toISOString()})).run();
  return {recorded:true};
}
