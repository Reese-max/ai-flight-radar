import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {startLocal} from '../scripts/local-server.mjs';
import {LocalD1} from '../scripts/sqlite-d1.mjs';

test('loopback HTTP serves real Worker handler and rejects unauthenticated POST',async t=>{
  const app=await startLocal({port:0});t.after(()=>app.close());
  const health=await fetch(app.url+'/api/health');assert.equal(health.status,200);
  assert.equal((await health.json()).app_id,'reese-max/ai-flight-radar:cloudflare-v1');
  const post=await fetch(app.url+'/api/scan/trigger',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
  assert.equal(post.status,503); // No development default password is invented.
  const rows=await fetch(app.url+'/api/ui/quotes');assert.deepEqual((await rows.json()).quotes,[]);
});
test('reopening the local SQLite database preserves task data',async t=>{
  const dir=await mkdtemp(path.join(tmpdir(),'radar-persist-'));t.after(()=>rm(dir,{recursive:true,force:true}));
  const file=path.join(dir,'test.db');let db=new LocalD1(file);
  db.sqlite.prepare('INSERT INTO cf_radar_tasks(id,query_key,origin,destination,depart_date,return_date) VALUES(?,?,?,?,?,?)')
    .run('key','key','TPE','FUK','2026-11-12','2026-11-16');db.close();db=new LocalD1(file);
  assert.equal(db.sqlite.prepare('SELECT COUNT(*) n FROM cf_radar_tasks').get().n,1);
  assert.equal(db.sqlite.prepare("SELECT value FROM cf_radar_meta WHERE key='task_count'").get().value,'1');db.close();
});
