/** Loopback-only offline API runner. Real SQLite, but NOT Cloudflare workerd. */
import http from 'node:http';
import {readFile,mkdir} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
import {LocalD1} from './sqlite-d1.mjs';
import worker from '../src/worker.mjs';
import {APP_ID} from '../src/catalog.mjs';
const project=fileURLToPath(new URL('../',import.meta.url));
const publicDir=path.join(project,'public');
const mime={'.html':'text/html; charset=utf-8','.css':'text/css','.js':'text/javascript','.mjs':'text/javascript','.svg':'image/svg+xml','.png':'image/png','.webp':'image/webp'};
export async function startLocal({port=8788,filename=':memory:',admin='',collector='',enabled=false,assets}={}){
  if(!Number.isInteger(port)||port<0||port>65535)throw new Error('Invalid port');
  const db=new LocalD1(filename),env={DB:db,APP_ID,ADMIN_KEY:admin,COLLECTOR_KEY:collector,COLLECTOR_ENABLED:enabled?'true':'false',
    MAX_SEARCHES_PER_HOUR:'3',ASSETS:{fetch:assets||(async(request)=>{
      let name;try{name=decodeURIComponent(new URL(request.url).pathname);}catch{return new Response('Bad path',{status:400});}
      const file=path.resolve(publicDir,'.'+(name==='/'?'/index.html':name));
      if(!file.startsWith(publicDir+path.sep)||!mime[path.extname(file)])return new Response('Not found',{status:404});
      try{return new Response(await readFile(file),{headers:{'Content-Type':mime[path.extname(file)]}});}
      catch{return new Response('UI not built. Apply this package to the original repository, then run npm run build.',{status:503});}
    })}};
  const server=http.createServer(async(req,res)=>{
    try{
      const chunks=[];let total=0;
      for await(const chunk of req){total+=chunk.length;if(total>16384){res.writeHead(413);res.end('Body too large');return;}chunks.push(chunk);}
      const address=server.address();
      const init={method:req.method,headers:req.headers};if(!['GET','HEAD'].includes(req.method))init.body=Buffer.concat(chunks);
      const response=await worker.fetch(new Request(`http://127.0.0.1:${address.port}${req.url}`,init),env);
      res.writeHead(response.status,Object.fromEntries(response.headers));res.end(Buffer.from(await response.arrayBuffer()));
    }catch{res.writeHead(503);res.end('Local test service failure');}
  });
  await new Promise(resolve=>server.listen(port,'127.0.0.1',resolve));
  return {server,db,url:`http://127.0.0.1:${server.address().port}`,close:()=>new Promise(resolve=>server.close(()=>{db.close();resolve();}))};
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  await mkdir(path.join(project,'.local'),{recursive:true});
  const app=await startLocal({filename:path.join(project,'.local','radar.sqlite'),
    admin:process.env.ADMIN_KEY||'',collector:process.env.COLLECTOR_KEY||'',enabled:process.env.COLLECTOR_ENABLED==='true'});
  console.log(`Local SQLite test runner: ${app.url}. Not Cloudflare, not a public deployment.`);
  for(const signal of ['SIGINT','SIGTERM'])process.once(signal,async()=>{await app.close();process.exit(0);});
}
