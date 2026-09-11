/** Read-only release checks, plus an unauthenticated write rejection probe. */
import {APP_ID} from '../src/catalog.mjs';
import {appendFile} from 'node:fs/promises';
const raw=process.env.CF_RADAR_URL||'',url=new URL(raw);
if(url.protocol!=='https:'||!/^ai-flight-radar-cf\.[a-z0-9-]+\.workers\.dev$/.test(url.hostname)||url.username||url.password||url.port||url.search||url.hash||url.pathname!=='/')throw new Error('Unexpected deployment URL');
async function get(path){const r=await fetch(new URL(path,url),{redirect:'error',signal:AbortSignal.timeout(20000)});if(!r.ok)throw new Error(`Verification HTTP ${r.status}: ${path}`);return r;}
const home=await get('/');if(!(await home.text()).includes('Flight Radar'))throw new Error('Unexpected homepage');
await get('/assets/app.js');
const health=await(await get('/api/health')).json();if(health.app_id!==APP_ID||health.schema_version!==1||health.demo!==false)throw new Error('Wrong API identity');
const config=await(await get('/api/ui/config')).json();if(config.worker.collector_enabled!==false)throw new Error('Initial collector must remain disabled');
if(['ADMIN_KEY','COLLECTOR_KEY','api_key','bot_token'].some(k=>Object.hasOwn(config,k)))throw new Error('Unexpected credential field');
const quotes=await(await get('/api/ui/quotes?limit=1')).json();if(quotes.demo!==false||!Array.isArray(quotes.quotes))throw new Error('Unexpected quotes contract');
const denied=await fetch(new URL('/api/scan/trigger',url),{method:'POST',headers:{'Content-Type':'application/json'},body:'{}',redirect:'error',signal:AbortSignal.timeout(20000)});
if(denied.status!==401)throw new Error('Unauthenticated writes did not return 401');
console.log(JSON.stringify({verified_url:url.origin,app_id:health.app_id,unauthorized_status:denied.status,collector_enabled:false}));
if(process.env.GITHUB_STEP_SUMMARY)await appendFile(process.env.GITHUB_STEP_SUMMARY,`## Verified website\n\n${url.origin}\n\nHomepage, assets, API identity, quote contract, and unauthenticated-write rejection passed. Live flight collection remains disabled.\n`);
