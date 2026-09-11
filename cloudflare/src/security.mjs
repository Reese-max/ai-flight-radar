import {HttpError,requireThat,digest} from './logic.mjs';
export const headers={
  'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store',
  'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','X-Frame-Options':'DENY',
  'Permissions-Policy':'camera=(), microphone=(), geolocation=()',
  'Content-Security-Policy':"default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
};
export function json(data,status=200,extra={}){return new Response(JSON.stringify(data),{status,headers:{...headers,...extra}});}
export async function authorize(request,env,role){
  const expected=role==='admin'?env.ADMIN_KEY:env.COLLECTOR_KEY;
  requireThat(typeof expected==='string'&&expected.length>=32&&expected.length<=256&&/^[\x21-\x7e]+$/.test(expected),
    'Server credential not configured',503);
  requireThat(!env.ADMIN_KEY||!env.COLLECTOR_KEY||env.ADMIN_KEY!==env.COLLECTOR_KEY,'Credentials must be separate',503);
  const supplied=role==='admin'?request.headers.get('X-API-Key'):
    request.headers.get('Authorization')?.match(/^Bearer (.+)$/)?.[1];
  requireThat(typeof supplied==='string'&&supplied.length<=256,'Valid credential required',401);
  const [a,b]=await Promise.all([digest(expected),digest(supplied)]);
  let different=0;for(let i=0;i<a.length;i++)different|=a.charCodeAt(i)^b.charCodeAt(i);
  requireThat(different===0,'Valid credential required',401);
}
export function sameOrigin(request){
  const origin=request.headers.get('Origin');
  requireThat(!origin||origin===new URL(request.url).origin,'Cross-origin writes are not allowed',403);
}
export async function bodyJSON(request){
  requireThat(request.headers.get('Content-Type')?.split(';')[0].trim()==='application/json','JSON required',415);
  const declared=request.headers.get('Content-Length');
  requireThat(!declared||(/^\d+$/.test(declared)&&Number(declared)<=16384),'Request body too large',413);
  const reader=request.body?.getReader();requireThat(Boolean(reader),'JSON body required',400);
  const chunks=[];let total=0;
  try{while(true){const {done,value}=await reader.read();if(done)break;total+=value.length;
    if(total>16384){await reader.cancel();throw new HttpError(413,'Request body too large');}chunks.push(value);}}
  finally{reader.releaseLock();}
  const all=new Uint8Array(total);let at=0;for(const c of chunks){all.set(c,at);at+=c.length;}
  try{return JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(all));}
  catch{throw new HttpError(400,'Malformed JSON');}
}
