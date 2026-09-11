/** Pure validation and statistics. No network or database side effects. */
import {origins,destinations} from './catalog.mjs';
export const DAY=86400000, TTL=6*3600000;
export class HttpError extends Error {
  constructor(status,detail,headers={}) {super(detail);this.status=status;this.headers=headers;}
}
export function requireThat(ok,detail='Invalid request',status=422){if(!ok)throw new HttpError(status,detail);}
export function record(value,keys){
  requireThat(value!==null&&typeof value==='object'&&!Array.isArray(value),'JSON object required');
  requireThat(Object.keys(value).every(k=>keys.includes(k)),'Unknown field');
  return value;
}
export function integer(value,min,max,name='number'){
  requireThat(Number.isSafeInteger(value)&&value>=min&&value<=max,`Invalid ${name}`);return value;
}
export function text(value,max,name='text'){
  requireThat(typeof value==='string'&&value.length>=1&&value.length<=max&&!/[\u0000-\u001f]/.test(value),`Invalid ${name}`);return value;
}
export function dateOnly(value){
  requireThat(typeof value==='string'&&/^20\d{2}-\d{2}-\d{2}$/.test(value),'Date must be YYYY-MM-DD');
  const ms=Date.parse(value+'T00:00:00Z');
  requireThat(Number.isFinite(ms)&&new Date(ms).toISOString().slice(0,10)===value,'Invalid calendar date');return value;
}
export function taipeiToday(now=Date.now()){return new Date(now+8*3600000).toISOString().slice(0,10);}
export function addDays(value,days){return new Date(Date.parse(dateOnly(value))+days*DAY).toISOString().slice(0,10);}
export function timestamp(value){
  requireThat(typeof value==='string'&&/^20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/.test(value),'Explicit timezone required');
  dateOnly(value.slice(0,10));
  const ms=Date.parse(value);requireThat(Number.isFinite(ms),'Invalid timestamp');
  const parts=value.slice(11,19).split(':').map(Number);
  requireThat(parts[0]<24&&parts[1]<60&&parts[2]<60,'Invalid time');
  return new Date(ms).toISOString();
}
export function codes(value,list){
  if(value===null||value===undefined||value==='')return [];
  requireThat(typeof value==='string'&&value.length<=100,'Invalid airport filter');
  const values=[...new Set(value.toUpperCase().split(','))];
  requireThat(values.every(v=>list.some(a=>a.code===v)),'Unsupported airport');return values;
}
export async function digest(value){
  const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(value));
  return [...new Uint8Array(bytes)].map(v=>v.toString(16).padStart(2,'0')).join('');
}
export async function taskSpec(input,now=Date.now()){
  record(input,['origin','destination','depart_date','return_date']);
  const os=codes(input.origin,origins),ds=codes(input.destination,destinations);
  requireThat(os.length===1&&ds.length===1,'One origin/destination required');
  const dep=dateOnly(input.depart_date),ret=dateOnly(input.return_date);
  const nights=(Date.parse(ret)-Date.parse(dep))/DAY;
  integer(nights,1,30,'trip duration');
  requireThat(dep>=taipeiToday(now)&&ret<=addDays(taipeiToday(now),366),'Dates must be within the next 366 days');
  const query_key=await digest([os[0],ds[0],dep,ret,'TWD','1','economy','direct',
    'google_flights','unverified-baggage-v1'].join('|'));
  return {id:query_key,query_key,origin:os[0],destination:ds[0],depart_date:dep,return_date:ret,trip_days:nights+1};
}
export function summarize(observations,before){
  const cutoff=Date.parse(before),daily=new Map();
  for(const row of observations){
    const at=Date.parse(row.searched_at),price=row.price_twd;
    if(!Number.isFinite(at)||at>=cutoff||at<cutoff-30*DAY||!Number.isSafeInteger(price)||price<=0)continue;
    const day=new Date(at).toISOString().slice(0,10);
    if(!daily.has(day))daily.set(day,[]);daily.get(day).push(price);
  }
  const medians=[...daily.values()].map(values=>{values.sort((a,b)=>a-b);const m=values.length>>1;
    return values.length%2?values[m]:(values[m-1]+values[m])/2;});
  const enough=medians.length>=5;
  return {prior_observed_days:medians.length,baseline_confident:enough,
    baseline_twd:enough?Math.round(medians.reduce((a,b)=>a+b,0)/medians.length*100)/100:null};
}
export function quoteView(payload,now=Date.now()){
  return {...payload,expired:Date.parse(payload.searched_at)<now-TTL||
    Date.parse(payload.searched_at)>now||payload.depart_date<taipeiToday(now)};
}
/** A conservative subset of the original rule parser. Always ask the UI to confirm. */
export function parseIntent(query,now=Date.now()){
  text(query,1000,'query');query=query.replaceAll('臺','台');
  const warnings=['僅解析規則與已有報價，不會自動全網搜尋；請核對所有條件。'];
  let selectedOrigins=origins.filter(a=>query.includes(a.code)||query.includes(a.city)||query.includes(a.name.slice(0,2))).map(a=>a.code);
  if(query.includes('桃園'))selectedOrigins=['TPE'];
  if(query.includes('松山'))selectedOrigins=['TSA'];
  if(query.includes('台灣')||selectedOrigins.length===0)selectedOrigins=origins.map(a=>a.code);
  const aliases={'東京':['NRT','HND'],'大阪':['KIX'],'關西':['KIX'],'京都':['KIX'],
    '福岡':['FUK'],'九州':['FUK','KMJ','KOJ'],'沖繩':['OKA'],'那霸':['OKA'],
    '札幌':['CTS'],'北海道':['CTS'],'名古屋':['NGO'],'仙台':['SDJ'],'熊本':['KMJ'],
    '鹿兒島':['KOJ'],'岡山':['OKJ'],'高松':['TAK']};
  const wanted=new Set(),excluded=new Set();
  for(const [name,items] of Object.entries(aliases)){
    if(new RegExp(`(?:不要|排除|不去)\\s*${name}`).test(query))items.forEach(x=>excluded.add(x));
    else if(query.includes(name))items.forEach(x=>wanted.add(x));
  }
  for(const a of destinations)if(query.includes(a.code))wanted.add(a.code);
  if(wanted.size===0)destinations.forEach(a=>wanted.add(a.code));
  excluded.forEach(x=>wanted.delete(x));
  let min=4,max=5;
  const duration=query.match(/(\d{1,2})\s*[~～至到\-]\s*(\d{1,2})\s*天/)||query.match(/(\d{1,2})\s*天/);
  if(duration){min=Number(duration[1]);max=Number(duration[2]||duration[1]);integer(min,2,31,'days');integer(max,min,31,'days');}
  let budget=null;
  const b=query.replaceAll(',','').match(/(?:NT\$\s*)?(\d{3,6})\s*(?:元|塊|以下|以內|內)/i);
  if(b)budget=integer(Number(b[1]),1,1000000,'budget');
  else if(/一萬|1萬/.test(query))budget=10000;
  const today=taipeiToday(now);let start=addDays(today,7),end=addDays(today,/半年|6個月/.test(query)?180:90);
  const dates=query.match(/20\d{2}-\d{2}-\d{2}/g);
  if(dates?.length){start=dateOnly(dates[0]);if(dates[1])end=dateOnly(dates[1]);}
  requireThat(end>start&&(Date.parse(end)-Date.parse(start))/DAY<=366,'Invalid date range');
  if(/月|寒假|暑假|週末|星期|連假/.test(query))warnings.push('月份、假期或週末語意可能未完整解析，請以篩選日期及模式為準。');
  if(/轉機/.test(query)&&!/不(?:要)?轉機/.test(query))warnings.push('此版本只提供直飛搜尋觀測，轉機條件不會套用。');
  return {intent:{origins:[...new Set(selectedOrigins)],destinations:[...wanted],min_duration:min,max_duration:max,
    max_budget_twd:budget,direct_only:true,start_date:start,end_date:end,summary_text:warnings.join('\n')},
    warnings,requires_confirmation:true,method:'rule_based'};
}
