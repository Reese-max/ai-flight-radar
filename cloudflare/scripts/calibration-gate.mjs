import {readFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {inspectAdmission} from '../src/calibration.mjs';

export async function currentAdmission(now=Date.now()){
  const raw=await readFile(new URL('../calibration/admission.json',import.meta.url),'utf8');
  return inspectAdmission(raw,now);
}

if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  const state=await currentAdmission();
  console.log(JSON.stringify({admitted:state.admitted,decision:state.decision,state:state.state,reason:state.reason,
    allowed_route_count:state.allowed_routes.length,expires_at:state.expires_at}));
  if(process.argv.includes('--require-admitted')&&!state.admitted)process.exitCode=1;
}
