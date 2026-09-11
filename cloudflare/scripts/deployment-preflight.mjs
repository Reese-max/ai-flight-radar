/** Report missing setting NAMES only; never prints or writes a credential. */
import {appendFile} from 'node:fs/promises';
export function inspectSettings(env){
  const names=['CLOUDFLARE_API_TOKEN','CLOUDFLARE_ACCOUNT_ID','CF_RADAR_DATABASE_ID','CF_RADAR_ADMIN_KEY','CF_RADAR_COLLECTOR_KEY'];
  const missing=names.filter(name=>!env[name]);
  const invalid=[];
  if(env.CLOUDFLARE_ACCOUNT_ID&&!/^[a-f0-9]{32}$/i.test(env.CLOUDFLARE_ACCOUNT_ID))invalid.push('CLOUDFLARE_ACCOUNT_ID');
  if(env.CF_RADAR_DATABASE_ID&&(!/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(env.CF_RADAR_DATABASE_ID)||/^0{8}-/.test(env.CF_RADAR_DATABASE_ID)))invalid.push('CF_RADAR_DATABASE_ID');
  for(const name of ['CF_RADAR_ADMIN_KEY','CF_RADAR_COLLECTOR_KEY'])if(env[name]&&!/^[!-~]{32,256}$/.test(env[name]))invalid.push(name);
  if(env.CF_RADAR_ADMIN_KEY&&env.CF_RADAR_ADMIN_KEY===env.CF_RADAR_COLLECTOR_KEY)invalid.push('ROLE_KEYS_MUST_DIFFER');
  return {ready:missing.length===0&&invalid.length===0,missing,invalid};
}
if(import.meta.url===new URL('file:'+process.argv[1]).href){
  const result=inspectSettings(process.env);
  console.log(JSON.stringify(result));
  if(process.env.GITHUB_OUTPUT)await appendFile(process.env.GITHUB_OUTPUT,`ready=${result.ready}\n`);
  if(process.env.GITHUB_STEP_SUMMARY)await appendFile(process.env.GITHUB_STEP_SUMMARY,
    `## Cloudflare deployment prerequisites\n\n${result.ready?'Settings are present; account authorization is NOT yet verified.':'NOT DEPLOYED: settings are missing or invalid.'}\n\nMissing: ${result.missing.join(', ')||'none'}\n\nInvalid: ${result.invalid.join(', ')||'none'}\n\nNo Cloudflare request was made by this check.\n`);
  if(process.argv.includes('--require-ready')&&!result.ready)process.exitCode=1;
}
