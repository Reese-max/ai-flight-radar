import {taipeiDate,addDays,money,isStale,relativeTime,sourceURL,hasBaseline,filteredQuotes,cleanWatches} from './logic.mjs';
const $ = id => document.getElementById(id);
const create = (tag, text='', className='') => {const n=document.createElement(tag); n.className=className; if(text) n.textContent=text; return n;};
const append = (parent,...children) => {children.forEach(c=>parent.append(c)); return parent;};
const button = (text,fn,cls='btn') => {const b=create('button',text,cls); b.type='button'; b.addEventListener('click',fn); return b;};
const titleFor = {explore:'探索低價',compare:'日期比較',watch:'追蹤清單',settings:'系統設定',detail:'票價詳情'};
const state = {view:'explore',config:null,quotes:[],mode:'all',sort:'recommended',nextOffset:null,
  filters:defaults(),apiKey:'',keyAuthorized:false,watchId:null,quoteController:null,loadVersion:0,routeVersion:0};
const STORE='flight-radar.watches.v1';
function defaults(){const today=taipeiDate();return {origin:'',destination:'',start_date:today,end_date:addDays(today,90),min_days:2,max_days:31,max_price:'',confident_only:false};}
let toastTimer;
function toast(text){$('toast').textContent=text;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,6000);}
function announce(text,error=false){const n=$('serviceNotice');n.textContent=text;n.className=error?'notice error':'notice';n.hidden=!text;}
function errorMessage(error){if(error.status===401)return '管理金鑰未通過驗證，請到系統設定重新確認。';if(error.status===429)return '請求太頻繁，請等候一分鐘再試。';if(error.status===404)return '找不到這筆資料，請返回探索並重新整理。';if(error.status===422)return '條件格式不正確，請檢查日期、機場與天數。';return '暫時無法連接資料服務。請稍後重試；這不代表沒有航班。';}
async function api(path,{method='GET',data,key=false,signal}={}){
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),20000);
  const cancel=()=>controller.abort();if(signal?.aborted)cancel();signal?.addEventListener('abort',cancel,{once:true});
  const headers={Accept:'application/json'};if(data!==undefined)headers['Content-Type']='application/json';if(key&&state.apiKey)headers['X-API-Key']=state.apiKey;
  try{const res=await fetch(path,{method,headers,signal:controller.signal,cache:'no-store',credentials:'same-origin',body:data===undefined?undefined:JSON.stringify(data)});
    if(!res.ok){const e=new Error('HTTP request failed');e.status=res.status;throw e;}
    if(!res.headers.get('content-type')?.includes('application/json'))throw new Error('API did not return JSON');return await res.json();
  }finally{clearTimeout(timer);signal?.removeEventListener('abort',cancel);}
}
function airport(code){return [...(state.config?.origins||[]),...(state.config?.destinations||[])].find(a=>a.code===code);}
function airportLabel(code){const a=airport(code);return a?`${a.city} ${code}`:code;}
function routeLabel(route){const [o,d]=route.split('/');return `${airportLabel(o)} → ${airportLabel(d)}`;}
function dateRange(q){return `${q.depart_date} — ${q.return_date}`;}
function option(value,label){const o=create('option',label);o.value=value;return o;}
function options(select,items,all){const old=select.value;select.replaceChildren();if(all)select.append(option('',all));items.forEach(i=>select.append(option(i.value,i.label)));if([...select.options].some(o=>o.value===old))select.value=old;}
function workerLabel(s){return ({idle:'運作中',scanning:'查價中',error:'批次異常',stopped:'已停止',stale:'心跳逾期',not_started:'尚未啟動'})[s]||'狀態未知';}
async function loadConfig(){
  try{const cfg=await api('/api/ui/config');state.config=cfg;
    const routeOptions=cfg.routes.map(r=>({value:`${r.origin}/${r.destination}`,label:routeLabel(`${r.origin}/${r.destination}`)}));
    ['historyRoute','scanRoute','watchRoute'].forEach(id=>options($(id),routeOptions));
    options($('filterOrigin'),cfg.origins.map(a=>({value:a.code,label:`${a.name} ${a.code}`})),'台灣所有機場');
    options($('filterDestination'),cfg.destinations.map(a=>({value:a.code,label:`${a.city} ${a.code}`})),'日本所有目的地');
    $('connectionBadge').textContent='已連接資料服務';$('connectionBadge').className='badge mint';$('apiStatus').textContent='可用';
    $('metricRoutes').textContent=cfg.routes.length;$('metricSnapshots').textContent=cfg.search_snapshots;
    $('metricWorker').textContent=workerLabel(cfg.worker.status);$('workerStatus').textContent=workerLabel(cfg.worker.status);
    $('workerHint').textContent=cfg.worker.heartbeat_at?`心跳：${relativeTime(cfg.worker.heartbeat_at)}`:'尚無有效心跳';
    $('ntfyState').textContent=cfg.notifications.ntfy?'伺服器已啟用':'未啟用';$('telegramState').textContent=cfg.notifications.telegram?'伺服器已啟用':'未啟用';
    $('notificationStatus').textContent=cfg.notifications.ntfy||cfg.notifications.telegram?'伺服器已啟用':'未啟用';
    $('lastQuoteAt').textContent=cfg.last_quote_at?`最近成功查價：${new Date(cfg.last_quote_at).toLocaleString('zh-TW',{timeZone:'Asia/Taipei'})}（台灣時間）`:'尚未有成功查價快照。';
    $('updatedAt').textContent=cfg.last_quote_at?relativeTime(cfg.last_quote_at):'等待第一次成功查價';
    if(!cfg.manual_scan_requires_key)$('scanStatus').textContent='本機模式；未設定管理金鑰';
    return true;
  }catch(e){$('connectionBadge').textContent='資料服務未連線';$('connectionBadge').className='badge amber';$('apiStatus').textContent='連線失敗';return false;}
}
function openDialog(id){const d=$(id);d.showModal();}
document.querySelectorAll('dialog').forEach(d=>{d.addEventListener('click',e=>{if(e.target===d){const r=d.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)d.close();}});});
function syncSummaries(){const f=state.filters;$('originSummary').textContent=f.origin?f.origin.split(',').map(airportLabel).join('、'):'台灣所有機場 ▾';$('destinationSummary').textContent=f.destination?f.destination.split(',').map(airportLabel).join('、'):'日本 ▾';$('datesSummary').textContent=`${f.start_date.slice(5)} – ${f.end_date.slice(5)} ▾`;$('durationSummary').textContent=f.min_days===2&&f.max_days===31?'不限天數 ▾':`${f.min_days}–${f.max_days} 天 ▾`;}
function openFilters(proposed=state.filters){const form=$('filterForm');for(const [name,value]of Object.entries(proposed)){const field=form.elements.namedItem(name);if(!field)continue;if(field.type==='checkbox')field.checked=Boolean(value);else{if(field.tagName==='SELECT'&&value&&![...field.options].some(o=>o.value===String(value)))field.append(option(value,`${value}（解析條件）`));field.value=String(value??'');}}$('filterError').textContent='';openDialog('filterDialog');}
function emptyState(container,title,text,actionLabel,action){container.replaceChildren();const box=create('div','','panel empty');const icon=create('img');icon.src='/assets/icons/radar.svg';icon.alt='';append(box,icon,create('h3',title),create('p',text,'secondary'));if(action)box.append(button(actionLabel,action,'btn primary'));container.append(box);}
function skeleton(){const frag=document.createDocumentFragment();for(let i=0;i<3;i++){const p=create('div','','panel skeleton');p.setAttribute('aria-hidden','true');for(let j=0;j<5;j++)p.append(create('div','','skeleton-line'+(j===1?' short':'')));frag.append(p);}$('results').replaceChildren(frag);}
function evidence(q){const stale=isStale(q), confident=hasBaseline(q);const box=create('div','',`evidence${stale?' stale':confident?'':' collecting'}`);
  const label=stale?'報價需要重新查證':confident?(q.drop_pct>0?`較同一行程觀測均價低 ${q.drop_pct}%`:'目前未低於同一行程觀測均價'):'歷史累積中，暫不判斷折扣';
  append(box,create('div',label),create('small',`${q.prior_observed_days} 個先前觀測日 · ${relativeTime(q.searched_at)}`));return box;
}
function detailHref(q){return `#detail/${encodeURIComponent(q.id)}`;}
function card(q){const card=create('article','',`panel flight-card${isStale(q)?' stale':''}`),head=create('div','','row between');
  append(head,append(create('div'),create('h3',airport(q.destination)?.city||q.destination),create('small','日本 · 已觀測報價','muted')),create('span',q.destination,'airport-code'));append(card,head,create('p',money(q.price_twd),'price'),create('small','每人來回 · 經濟艙 · 非最終含費總價','muted'),create('hr'),create('p',`${airportLabel(q.origin)} → ${airportLabel(q.destination)}`,'flight-meta'),create('p',`${q.depart_date.slice(5)}–${q.return_date.slice(5)} · ${q.trip_days} 天 ${q.trip_days-1} 夜`,'flight-meta'),create('p','直飛搜尋 · 行李與完整航段待確認','small amber'),evidence(q));
  const link=create('a','查看票價詳情','btn'+(hasBaseline(q)&&!isStale(q)?' primary':''));link.href=detailHref(q);card.append(link);return card;
}
function renderQuotes(){const rows=filteredQuotes(state.quotes,state.mode,state.filters.confident_only,state.sort,state.config?.destinations||[]);$('resultCount').textContent=`${rows.length} 筆報價`;$('results').setAttribute('aria-busy','false');
  if(!rows.length){const never=state.config?.search_snapshots===0;emptyState($('results'),never?'還沒有成功查價紀錄':'目前載入範圍沒有符合條件的報價',never?'資料庫尚未收集到報價。管理員可在系統設定查價；本站不會填入示範機票。':'可以放寬日期、預算或模式；有更多資料時也可按下方「載入更多」。','調整搜尋條件',()=>openFilters());}
  else $('results').replaceChildren(...rows.map(card));
  $('resultNote').textContent=`已載入 ${state.quotes.length} 組最新觀測；排序與模式套用於已載入範圍。${state.mode==='leave'?'請假採保守平日計數，不假設國定假日。':''}`;
  $('loadMore').hidden=state.nextOffset===null;
}
async function loadQuotes(more=false){state.quoteController?.abort();const controller=new AbortController();state.quoteController=controller;const version=++state.loadVersion;
  const f=state.filters,params=new URLSearchParams();for(const k of ['origin','destination','start_date','end_date','min_days','max_days','max_price'])if(f[k]!==''&&f[k]!=null)params.set(k,f[k]);params.set('limit','48');params.set('sort',state.sort==='recent'?'recent':'price');params.set('offset',more?state.nextOffset||0:0);
  $('results').setAttribute('aria-busy','true');$('loadMore').disabled=true;if(!state.quotes.length)skeleton();
  try{const data=await api(`/api/ui/quotes?${params}`,{signal:controller.signal});if(version!==state.loadVersion)return;if(!Array.isArray(data.quotes))throw new Error('Invalid quotes');state.quotes=more?[...state.quotes,...data.quotes.filter(q=>!state.quotes.some(old=>old.id===q.id))]:data.quotes;state.nextOffset=data.next_offset??null;announce('');renderQuotes();}
  catch(e){if(controller.signal.aborted)return;announce(state.quotes.length?'更新失敗，保留上次載入的報價與時間；請勿視為即時價格。':errorMessage(e),true);if(state.quotes.length)renderQuotes();else{emptyState($('results'),'資料暫時無法載入','這是連線問題，不代表查無航班。','重新讀取',()=>loadQuotes());$('resultCount').textContent='連線失敗';}$('results').setAttribute('aria-busy','false');}
  finally{if(version===state.loadVersion)$('loadMore').disabled=false;}
}
async function loadHistory(){const route=$('historyRoute').value;if(!route){emptyState($('historyRows'),'尚未取得航線','請先確認資料服務已連線。','重新讀取',async()=>{await loadConfig();loadHistory();});return;}const current=++state.routeVersion;$('historyRows').replaceChildren(create('p','正在讀取日期組合…','muted'));
  try{const data=await api(`/api/ui/dates/${route}`);if(current!==state.routeVersion)return;if(!data.quotes.length){emptyState($('historyRows'),'這條航線尚無日期快照','需要成功查價後，才能比較已觀測的日期。');return;}
    $('historyRows').replaceChildren(...data.quotes.map(q=>{const row=button('',()=>location.hash=detailHref(q),'date-row');const left=create('span',`${q.depart_date} — ${q.return_date}`);left.append(create('small',`${q.trip_days} 天 · ${q.prior_observed_days} 個先前觀測日${isStale(q)?' · 報價過期':''}`));append(row,left,create('span',money(q.price_twd),'data'));return row;}));if(data.truncated)$('historyRows').append(create('p','僅列出前 180 組日期。','small muted'));
  }catch(e){if(current===state.routeVersion)emptyState($('historyRows'),'日期資料未能載入',errorMessage(e),'稍後重試',loadHistory);}
}
function keyValue(key,value,cls=''){const row=create('div','','kv');return append(row,create('span',key),create('span',value,cls));}
function sourceLink(q){const u=sourceURL(q);if(!u){const b=button('來源連結尚未確認',()=>{});b.disabled=true;return b;}const a=create('a',isStale(q)?'到來源重新查證 ↗':'前往來源網站查證 ↗','btn primary');a.href=u;a.target='_blank';a.rel='noopener noreferrer';return a;}
async function showDetail(id){const current=++state.routeVersion;$('detailContent').replaceChildren(create('p','正在讀取票價詳情…','muted'));
  try{const q=await api(`/api/ui/quote/${encodeURIComponent(id)}`);if(current!==state.routeVersion)return;const wrap=create('div','','stack');const title=create('h1',`${airport(q.destination)?.city||q.destination} ${q.destination}`);title.id='detailHeading';wrap.append(title,create('p',`${airportLabel(q.origin)} → ${airportLabel(q.destination)} · ${dateRange(q)}`,'secondary'));
    const columns=create('div','','two-col mt'),left=create('div','','stack'),right=create('aside','','panel stack detail-card');
    const evidencePanel=create('article','','panel stack');evidencePanel.append(create('h2','價格依據'),evidence(q));
    if(hasBaseline(q))evidencePanel.append(keyValue('同一行程先前觀測均價',money(q.baseline_twd)),keyValue('先前觀測日',`${q.prior_observed_days} 日`));
    evidencePanel.append(create('p','比較相同查詢的先前資料；最新報價不納入自己的比較基準。','small muted'),button('查看比較方法',()=>openDialog('methodDialog'),'btn'));
    const verify=create('article','','panel stack');verify.append(create('h3','訂票前再確認'),create('p','來回航段與起降時間、手提／托運行李、付款附加費，以及退改票規則，皆需在來源網站確認。','secondary'),create('p','本站不自動訂票或付款。','small amber'));
    left.append(evidencePanel,verify,button('比較其他日期',()=>{const route=`${q.origin}/${q.destination}`;if(![...$('historyRoute').options].some(o=>o.value===route))$('historyRoute').append(option(route,routeLabel(route)));$('historyRoute').value=route;location.hash='#compare';}));
    right.append(create('p','最近一次觀測報價','secondary'),create('p',money(q.price_twd),'price hero'),create('small','每人來回 · 1 位成人 · 經濟艙','muted'),evidence(q),create('hr'),keyValue('出發／回程',dateRange(q)),keyValue('旅行長度',`${q.trip_days} 天 ${q.trip_days-1} 夜`),keyValue('航空公司',q.airline||'待來源確認'),keyValue('托運行李','待來源網站確認','amber'),keyValue('資料來源',q.source));
    const actions=create('div','','sticky-actions');actions.append(sourceLink(q),button('追蹤',()=>openWatch(null,{route:`${q.origin}/${q.destination}`,budget:q.price_twd,name:`${airport(q.destination)?.city||q.destination}・等一張好價格`})));right.append(actions,create('p',`查價時間：${new Date(q.searched_at).toLocaleString('zh-TW',{timeZone:'Asia/Taipei'})}（台灣時間）`,'small muted'),create('p','這是比價搜尋連結，不保證仍有相同價格或可售座位。','small muted'));columns.append(left,right);wrap.append(columns);$('detailContent').replaceChildren(wrap);
  }catch(e){if(current===state.routeVersion)emptyState($('detailContent'),'無法開啟這筆報價',errorMessage(e),'返回探索',()=>location.hash='#explore');}
}
function readWatches(){try{return cleanWatches(JSON.parse(localStorage.getItem(STORE)||'[]'));}catch{return [];}}
function saveWatches(rows){try{localStorage.setItem(STORE,JSON.stringify(cleanWatches(rows)));return true;}catch{toast('瀏覽器無法儲存資料，條件尚未保存。');return false;}}
function openWatch(id=null,preset={}){const old=id?readWatches().find(w=>w.id===id):null;state.watchId=id;const f=$('watchForm');f.reset();f.elements.name.value=old?.name||preset.name||'';f.elements.budget.value=old?.budget||preset.budget||8000;f.elements.enabled.checked=old?.enabled!==false;const route=old?.route||preset.route||$('scanRoute').value;if(route&&![...$('watchRoute').options].some(o=>o.value===route))$('watchRoute').append(option(route,routeLabel(route)));$('watchRoute').value=route;$('watchError').textContent='';openDialog('watchDialog');}
function renderWatches(){const rows=readWatches();if(!rows.length){emptyState($('watchRows'),'把想去的地方，先留下來。','新增一組目標航線與預算。清單只保存在這個瀏覽器，不會自動發送通知。','新增追蹤',()=>openWatch());return;}$('watchRows').replaceChildren(...rows.map(w=>{const c=create('article','',`panel watch-card${w.enabled?'':' paused'}`);c.append(create('h3',w.name),create('p',routeLabel(w.route),'secondary'),create('p',`目標來回票價 ${money(w.budget)}`,'mint data'),create('small',w.enabled?'已儲存 · 只限此瀏覽器':'已暫停 · 不套用此條件','amber'));const actions=create('div','','watch-actions');actions.append(button('用這組條件搜尋',()=>{const [origin,destination]=w.route.split('/');state.filters={...defaults(),origin,destination,max_price:w.budget};syncSummaries();location.hash='#explore';if(state.view==='explore')loadQuotes();}),button('編輯',()=>openWatch(w.id)),button(w.enabled?'暫停':'啟用',()=>{if(saveWatches(rows.map(x=>x.id===w.id?{...x,enabled:!x.enabled}:x)))renderWatches();}),button('刪除',()=>{if(confirm(`刪除「${w.name}」這組本機條件？`)&&saveWatches(rows.filter(x=>x.id!==w.id)))renderWatches();},'btn quiet danger'));c.append(actions);return c;}));}
function navigate(){const [raw,id]=location.hash.slice(1).split('/');if(raw==='main'){$('main').focus();return;}state.view=Object.hasOwn(titleFor,raw)?raw:'explore';state.routeVersion++;document.querySelectorAll('[data-nav]').forEach(a=>{if(a.dataset.nav===(state.view==='detail'?'explore':state.view))a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});for(const key of Object.keys(titleFor))$(`${key}Page`).hidden=key!==state.view;$('breadcrumb').textContent=`工作台 / ${titleFor[state.view]}`;document.title=`${titleFor[state.view]}｜Flight Radar`;window.scrollTo(0,0);$('main').focus({preventScroll:true});if(state.view==='compare')loadHistory();else if(state.view==='detail')showDetail(id||'');else if(state.view==='watch')renderWatches();else if(state.view==='settings')loadConfig();else if(state.config)loadQuotes();}
$('filterForm').addEventListener('submit',e=>{e.preventDefault();const d=new FormData(e.currentTarget),f={origin:d.get('origin'),destination:d.get('destination'),start_date:d.get('start_date'),end_date:d.get('end_date'),min_days:Number(d.get('min_days')),max_days:Number(d.get('max_days')),max_price:d.get('max_price')?Number(d.get('max_price')):'',confident_only:d.has('confident_only')};const span=(Date.parse(f.end_date)-Date.parse(f.start_date))/86400000;
  if(!Number.isFinite(span)||span<=0||span>366||f.min_days>f.max_days){$('filterError').textContent='回程上限須晚於出發日，範圍不能超過 366 天；最多天數不可小於最少天數。';return;}state.filters=f;syncSummaries();$('filterDialog').close();state.quotes=[];state.nextOffset=null;if(state.view!=='explore')location.hash='#explore';else loadQuotes();});
$('resetFilters').addEventListener('click',()=>{const d=defaults();const f=$('filterForm');for(const[k,v]of Object.entries(d)){const n=f.elements.namedItem(k);if(n.type==='checkbox')n.checked=v;else n.value=v;}$('filterError').textContent='';});
$('searchForm').addEventListener('submit',async e=>{e.preventDefault();const query=$('nlpQuery').value.trim();if(!query){openFilters();return;}$('searchButton').disabled=true;try{const {intent}=await api('/api/ui/parse',{method:'POST',data:{query}});const origins=(intent.origins||[]).filter(c=>state.config?.origins.some(a=>a.code===c));const destinations=(intent.destinations||[]).filter(c=>state.config?.destinations.some(a=>a.code===c));const f={...defaults(),origin:origins.join(','),destination:destinations.join(','),start_date:intent.start_date,end_date:intent.end_date,min_days:intent.min_duration,max_days:intent.max_duration,max_price:intent.max_budget_twd||''};$('queryNote').textContent='已解析條件，請在篩選視窗核對後套用。規則解析可能無法理解排除條件或節日。';$('queryNote').hidden=false;openFilters(f);}catch(e){toast(errorMessage(e));}finally{$('searchButton').disabled=false;}});
$('sortSelect').addEventListener('change',()=>{state.sort=$('sortSelect').value;loadQuotes();});
document.querySelectorAll('[data-mode]').forEach(b=>b.addEventListener('click',()=>{state.mode=b.dataset.mode;document.querySelectorAll('[data-mode]').forEach(n=>n.setAttribute('aria-pressed',String(n===b)));renderQuotes();}));
$('loadMore').addEventListener('click',()=>loadQuotes(true));$('historyRoute').addEventListener('change',loadHistory);
$('watchForm').addEventListener('submit',e=>{e.preventDefault();const f=new FormData(e.currentTarget),item={id:state.watchId||crypto.randomUUID(),name:String(f.get('name')).trim(),route:f.get('route'),budget:Number(f.get('budget')),enabled:f.has('enabled')};if(!item.name||!cleanWatches([item]).length){$('watchError').textContent='請填入名稱、有效航線與大於零的預算。';return;}const rows=readWatches();if(!state.watchId&&rows.length>=100){$('watchError').textContent='此瀏覽器最多保存 100 組條件。';return;}const updated=rows.some(w=>w.id===item.id)?rows.map(w=>w.id===item.id?item:w):[...rows,item];if(saveWatches(updated)){$('watchDialog').close();toast('條件已儲存在此瀏覽器；沒有啟動推播。');if(state.view==='watch')renderWatches();}});
$('apiKey').addEventListener('input',()=>{state.apiKey=$('apiKey').value;state.keyAuthorized=false;$('keyStatus').textContent='金鑰已變更，請重新驗證';});
$('verifyKey').addEventListener('click',async()=>{state.apiKey=$('apiKey').value;$('verifyKey').disabled=true;try{await api('/api/ui/access',{key:true});state.keyAuthorized=true;$('keyStatus').textContent='管理金鑰驗證成功；只保留在本分頁。';}catch(e){state.keyAuthorized=false;$('keyStatus').textContent=errorMessage(e);}finally{$('verifyKey').disabled=false;}});
$('clearKey').addEventListener('click',()=>{state.apiKey='';state.keyAuthorized=false;$('apiKey').value='';$('keyStatus').textContent='本分頁金鑰已清除';});
$('scanButton').addEventListener('click',async()=>{if(!state.config){toast('請先確認 API 連線。');return;}if(state.config.manual_scan_requires_key&&!state.keyAuthorized){$('scanStatus').textContent='請先驗證管理金鑰。';$('apiKey').focus();return;}const route=$('scanRoute').value;if(!route){toast('請選擇航線。');return;}const [origin,destination]=route.split('/');$('scanButton').disabled=true;$('scanStatus').textContent='正在提交一次查價任務…';try{await api('/api/scan/trigger',{method:'POST',data:{origin,destination},key:true});$('scanStatus').textContent='已提交一個任務；不代表已取得新報價，也未啟動持續掃描。';toast('查價已提交，稍後重新整理查看實際快照。');}catch(e){$('scanStatus').textContent=errorMessage(e);}finally{setTimeout(()=>$('scanButton').disabled=false,60000);}});
document.addEventListener('click',e=>{const close=e.target.closest('[data-close]');if(close){$(close.dataset.close).close();return;}const action=e.target.closest('[data-action]')?.dataset.action;if(action==='filters')openFilters();if(action==='method')openDialog('methodDialog');if(action==='new-watch')openWatch();if(action==='refresh')refresh();});
async function refresh(){const ok=await loadConfig();if(!ok)announce('API 連線失敗，請稍後重試。',true);if(state.view==='explore')loadQuotes();else if(state.view==='compare')loadHistory();else if(state.view==='detail')showDetail(location.hash.split('/')[1]||'');else if(state.view==='watch')renderWatches();}
window.addEventListener('hashchange',navigate);window.addEventListener('storage',e=>{if(e.key===STORE&&state.view==='watch')renderWatches();});
// Refresh only the already-collected dataset. Never auto-trigger a paid/live search.
setInterval(()=>{if(!document.hidden&&!document.querySelector('dialog[open]')&&['explore','settings'].includes(state.view))refresh();},60000);
syncSummaries();skeleton();await loadConfig();navigate();if(state.view==='explore'&&!state.config)loadQuotes();
