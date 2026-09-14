/** Generates a local config file only. Never invokes Cloudflare. */
import {readFile,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
export function configured(base,databaseId,accountId,collectorEnabled,maxSearchesPerHour){
  if(!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(databaseId||'')||databaseId==='00000000-0000-0000-0000-000000000000')throw new Error('Use a real D1 database UUID');
  if(!/^[0-9a-f]{32}$/i.test(accountId||''))throw new Error('Use a 32-character Cloudflare account ID');
  if(base.name!=='ai-flight-radar-cf'||base.d1_databases?.length!==1||base.d1_databases[0].binding!=='DB')throw new Error('Unexpected deployment target');
  const out=structuredClone(base);out.account_id=accountId;out.d1_databases[0].database_id=databaseId;
  if(collectorEnabled==='true'||collectorEnabled==='false')out.vars={...out.vars,COLLECTOR_ENABLED:collectorEnabled};
  const cap=Number(maxSearchesPerHour);
  if(Number.isInteger(cap)&&cap>=1&&cap<=10)out.vars={...out.vars,MAX_SEARCHES_PER_HOUR:String(cap)};
  return out;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  const root=new URL('../',import.meta.url),base=JSON.parse(await readFile(new URL('wrangler.json',root),'utf8'));
  const config=configured(base,process.env.CF_RADAR_DATABASE_ID,process.env.CLOUDFLARE_ACCOUNT_ID,
    process.env.CF_RADAR_COLLECTOR_ENABLED,process.env.CF_RADAR_MAX_SEARCHES_PER_HOUR);
  await writeFile(new URL('wrangler.deploy.json',root),JSON.stringify(config,null,2)+'\n',{flag:'wx'});
  console.log('Created local wrangler.deploy.json. No resource was created or deployed.');
}
