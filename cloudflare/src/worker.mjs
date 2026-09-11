import {APP_ID} from './catalog.mjs';
import {HttpError,requireThat,record,parseIntent} from './logic.mjs';
import {json,authorize,sameOrigin,bodyJSON} from './security.mjs';
import * as store from './store.mjs';
/** Clock injection is only used by offline tests; Cloudflare uses Date.now. */
export function createHandler(clock=Date.now){
  return {async fetch(request,env){
    const url=new URL(request.url),p=url.pathname,method=request.method;
    if(!p.startsWith('/api/')&&p!=='/api')return env.ASSETS.fetch(request);
    try{
      const now=clock();
      if(!['GET','POST'].includes(method))throw new HttpError(405,'Method not allowed',{'Allow':'GET, POST'});
      // Authenticate writes before parsing any supplied body or touching the DB.
      if(method==='POST'){
        sameOrigin(request);
        if(p.startsWith('/api/collector/'))await authorize(request,env,'collector');
        else if(p.startsWith('/api/admin/')||p==='/api/scan/trigger')await authorize(request,env,'admin');
        else if(p!=='/api/ui/parse')throw new HttpError(404,'API route not found');
      }
      if(p==='/api/ui/access'&&method==='GET')await authorize(request,env,'admin');
      await store.ready(env);
      if(method==='GET'){
        if(p==='/api/health')return json({status:'ok',app_id:APP_ID,schema_version:1,ui_version:'2.0-cf',demo:false});
        if(p==='/api/ui/config')return json(await store.config(env,now));
        if(p==='/api/ui/access')return json({authorized:true});
        if(p==='/api/ui/quotes')return json(await store.quotes(env.DB,url.searchParams,now));
        const match=p.match(/^\/api\/ui\/quote\/([^/]+)$/);
        if(match)return json(await store.detail(env.DB,match[1],now));
        const route=p.match(/^\/api\/ui\/dates\/([^/]+)\/([^/]+)$/);
        if(route)return json(await store.dates(env.DB,route[1],route[2],now));
      }else{
        const data=await bodyJSON(request);
        if(p==='/api/ui/parse'){record(data,['query']);return json(parseIntent(data.query,now));}
        if(p==='/api/scan/trigger')return json(await store.enqueue(env,data,now),202);
        if(p==='/api/admin/tasks')return json(await store.seed(env.DB,data,now),202);
        if(p==='/api/collector/claim')return json(await store.claim(env,data,now));
        if(p==='/api/collector/result')return json(await store.complete(env,data,now));
        if(p==='/api/collector/report')return json(await store.report(env,data,now));
      }
      throw new HttpError(404,'API route not found');
    }catch(error){
      if(error instanceof HttpError)return json({detail:error.message},error.status,error.headers);
      // No SQL, request headers, keys, upstream HTML, or stack traces in responses.
      if(/capacity reached/.test(String(error?.message)))return json({detail:'Storage guard reached; review backup and capacity before collecting more'},503);
      return json({detail:'Data service is unavailable; this does not mean there are no flights'},503);
    }
  }};
}
export default createHandler();
