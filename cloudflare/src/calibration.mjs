import {routes} from './catalog.mjs';

export const PROVIDER='fast_flights';
export const PROVIDER_VERSION='3.1.0';
export const PROTOCOL_VERSION='1.0';
export const OUTCOMES=Object.freeze(['SUCCESS','NO_RESULTS','RATE_LIMITED','UPSTREAM_CHANGED','PARSE_FAILED','BLOCKED']);
export const ERROR_TYPES=Object.freeze(['RATE_LIMITED','UPSTREAM_CHANGED','PARSE_FAILED','TIMEOUT','BLOCKED','SOURCE_UNAVAILABLE','UNKNOWN']);
export const ROUTE_KEYS=Object.freeze(routes.map(route=>route.origin+'/'+route.destination));
export const DATE_WINDOWS=Object.freeze([30,90,180]);
export const THRESHOLDS=Object.freeze({
  minimumSamplesPerRoute:3,
  minimumSearchSuccessRate:0.9,
  minimumParseCompletenessRate:0.98,
  maximumQuoteAgeP95Seconds:6*60*60,
  minimumConsistencyRate:1,
  minimumSafeLinkRate:1,
  minimumHandoffComparisons:3,
  maximumPriceDiscrepancyP95Percent:5,
  maximumReceiptAgeMs:14*24*60*60*1000,
});

const hardStopOutcomes=new Set(['RATE_LIMITED','UPSTREAM_CHANGED','PARSE_FAILED','BLOCKED']);
const reasonCodes=new Set([
  'authorization_missing','terms_unclear','budget_unapproved','unsupported_profile','owner_stop',
  'provider_rate_limit','schema_change','partial_payload','upstream_unavailable','source_unavailable',
  'owner_authorized_live_calibration_not_completed','invalid_or_unredacted_observation',
  'sample_budget_exceeded','stop_rule_triggered','no_route_meets_predeclared_thresholds',
]);
const isObject=value=>value!==null&&typeof value==='object'&&!Array.isArray(value);
const validTime=value=>typeof value==='string'&&Number.isFinite(Date.parse(value));
const knownRoute=value=>ROUTE_KEYS.includes(value);
const receiptKeys=new Set(['schema_version','protocol_version','provider','provider_version','decision','measured_at',
  'expires_at','allowed_routes','route_metrics','blockers','approvals']);
const approvalKeys=['owner_authorized','terms_allowed','budget_approved'];
function validApprovals(value){
  return isObject(value)&&Object.keys(value).length===approvalKeys.length&&
    approvalKeys.every(key=>typeof value[key]==='boolean');
}

function invalid(reason='invalid_receipt'){
  return {admitted:false,state:'invalid',reason,decision:'BLOCK',allowed_routes:[],measured_at:null,expires_at:null};
}

function finiteRate(value){
  return typeof value==='number'&&Number.isFinite(value)&&value>=0&&value<=1;
}

function routeMetricPass(metric){
  return isObject(metric)&&
    Number.isInteger(metric.attempted)&&metric.attempted===DATE_WINDOWS.length&&
    Number.isInteger(metric.successful)&&metric.successful>=THRESHOLDS.minimumSamplesPerRoute&&
    Number.isInteger(metric.parse_complete)&&metric.parse_complete>=THRESHOLDS.minimumSamplesPerRoute&&
    Number.isInteger(metric.parse_sample_count)&&metric.parse_sample_count===metric.attempted&&
    Array.isArray(metric.date_windows)&&metric.date_windows.length===DATE_WINDOWS.length&&
    DATE_WINDOWS.every((days,index)=>metric.date_windows[index]===days)&&
    Number.isInteger(metric.quote_age_sample_count)&&metric.quote_age_sample_count===metric.successful&&
    ['currency_match_count','passenger_match_count','cabin_match_count','directness_match_count','safe_link_resolved_count']
      .every(key=>Number.isInteger(metric[key])&&metric[key]===metric.successful)&&
    finiteRate(metric.search_success_rate)&&metric.search_success_rate>=THRESHOLDS.minimumSearchSuccessRate&&
    finiteRate(metric.parse_completeness_rate)&&metric.parse_completeness_rate>=THRESHOLDS.minimumParseCompletenessRate&&
    typeof metric.quote_age_p95_seconds==='number'&&Number.isFinite(metric.quote_age_p95_seconds)&&metric.quote_age_p95_seconds>=0&&metric.quote_age_p95_seconds<=THRESHOLDS.maximumQuoteAgeP95Seconds&&
    ['currency_consistency_rate','passenger_consistency_rate','cabin_consistency_rate','directness_consistency_rate']
      .every(key=>finiteRate(metric[key])&&metric[key]>=THRESHOLDS.minimumConsistencyRate)&&
    finiteRate(metric.safe_link_resolution_rate)&&metric.safe_link_resolution_rate>=THRESHOLDS.minimumSafeLinkRate&&
    Number.isInteger(metric.handoff_comparison_count)&&metric.handoff_comparison_count>=THRESHOLDS.minimumHandoffComparisons&&
    typeof metric.price_discrepancy_p95_percent==='number'&&Number.isFinite(metric.price_discrepancy_p95_percent)&&metric.price_discrepancy_p95_percent>=0&&metric.price_discrepancy_p95_percent<=THRESHOLDS.maximumPriceDiscrepancyP95Percent;
}

const metricKeys=new Set([
  'attempted','successful','parse_complete','parse_sample_count','date_windows','quote_age_sample_count',
  'currency_match_count','passenger_match_count','cabin_match_count','directness_match_count','safe_link_resolved_count',
  'search_success_rate','parse_completeness_rate',
  'quote_age_p95_seconds','currency_consistency_rate','passenger_consistency_rate',
  'cabin_consistency_rate','directness_consistency_rate','safe_link_resolution_rate',
  'handoff_comparison_count','price_discrepancy_p95_percent',
]);

export function inspectAdmission(value,now=Date.now()){
  let receipt=value;
  if(typeof value==='string'){
    try{receipt=JSON.parse(value);}catch{return invalid();}
  }
  if(!isObject(receipt)||Object.keys(receipt).some(key=>!receiptKeys.has(key))||!validApprovals(receipt.approvals)||
    !Array.isArray(receipt.blockers)||receipt.blockers.some(reason=>!reasonCodes.has(reason))||
    receipt.schema_version!==1||receipt.protocol_version!==PROTOCOL_VERSION||
    receipt.provider!==PROVIDER||receipt.provider_version!==PROVIDER_VERSION||
    !['BUILD','NARROW','BLOCK'].includes(receipt.decision)||!isObject(receipt.route_metrics)||
    Object.keys(receipt.route_metrics).some(route=>!knownRoute(route)||!isObject(receipt.route_metrics[route])||
      Object.keys(receipt.route_metrics[route]).some(key=>!metricKeys.has(key)))||
    !Array.isArray(receipt.allowed_routes)||receipt.allowed_routes.some(route=>!knownRoute(route)))return invalid();
  if(receipt.decision==='BLOCK'){
    if(receipt.blockers.length===0||receipt.allowed_routes.length!==0)return invalid();
    return {admitted:false,state:'blocked',reason:'calibration_blocked',decision:'BLOCK',
      allowed_routes:[],measured_at:null,expires_at:null};
  }
  if(receipt.blockers.length>0||!approvalKeys.every(key=>receipt.approvals[key]===true))return invalid();
  if(!validTime(receipt.measured_at)||!validTime(receipt.expires_at))return invalid();
  const measured=Date.parse(receipt.measured_at),expires=Date.parse(receipt.expires_at);
  if(measured>now+5*60*1000||expires<=measured||expires-measured>THRESHOLDS.maximumReceiptAgeMs)return invalid();
  if(now>=expires)return {admitted:false,state:'expired',reason:'calibration_expired',decision:receipt.decision,
    allowed_routes:[],measured_at:receipt.measured_at,expires_at:receipt.expires_at};
  if(receipt.allowed_routes.length===0||
    new Set(receipt.allowed_routes).size!==receipt.allowed_routes.length||!receipt.allowed_routes.every(knownRoute)||
    !isObject(receipt.route_metrics))return invalid();
  const metricRoutes=Object.keys(receipt.route_metrics);
  if(metricRoutes.some(route=>!knownRoute(route))||
    receipt.allowed_routes.some(route=>!receipt.route_metrics[route])||
    receipt.allowed_routes.some(route=>!routeMetricPass(receipt.route_metrics[route])))return invalid();
  if(receipt.decision==='BUILD'&&ROUTE_KEYS.some(route=>!receipt.allowed_routes.includes(route)))return invalid();
  if(receipt.decision==='NARROW'&&receipt.allowed_routes.length>=ROUTE_KEYS.length)return invalid();
  return {admitted:true,state:'current',reason:'calibration_current',decision:receipt.decision,
    allowed_routes:[...receipt.allowed_routes],measured_at:receipt.measured_at,expires_at:receipt.expires_at};
}

const observationKeys=new Set([
  'outcome','route','queried_at','depart_date','profile','reason_code','parse_complete','quote_age_seconds',
  'observed_currency','observed_adults','observed_cabin','observed_direct_only','link_resolution',
  'displayed_price_twd','handoff_price_twd','handoff_checked_at',
]);
const quoteKeys=new Set([
  'parse_complete','quote_age_seconds','observed_currency','observed_adults','observed_cabin',
  'observed_direct_only','link_resolution','displayed_price_twd','handoff_price_twd','handoff_checked_at',
]);

function dateWindowDays(item){
  if(typeof item.depart_date!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(item.depart_date))return null;
  const departure=Date.parse(item.depart_date+'T00:00:00.000Z');
  if(!Number.isFinite(departure)||new Date(departure).toISOString().slice(0,10)!==item.depart_date)return null;
  const taipeiToday=new Date(Date.parse(item.queried_at)+8*60*60*1000).toISOString().slice(0,10);
  return (departure-Date.parse(taipeiToday+'T00:00:00.000Z'))/86400000;
}

export function validateObservation(item){
  if(!isObject(item)||Object.keys(item).some(key=>!observationKeys.has(key))||
    !OUTCOMES.includes(item.outcome)||!knownRoute(item.route)||!validTime(item.queried_at)||
    !DATE_WINDOWS.includes(dateWindowDays(item))||!isObject(item.profile))return false;
  const {trip_type,adults,cabin,direct_only}=item.profile;
  if(Object.keys(item.profile).some(key=>!['trip_type','adults','cabin','direct_only'].includes(key))||
    !['one_way','round_trip'].includes(trip_type)||!Number.isInteger(adults)||adults<1||adults>9||
    !['economy','premium_economy','business','first'].includes(cabin)||typeof direct_only!=='boolean')return false;
  const supportedProfile=trip_type==='round_trip'&&adults===1&&cabin==='economy'&&direct_only===true;
  if(!supportedProfile&&item.outcome!=='BLOCKED')return false;
  if(item.outcome!=='SUCCESS'){
    if([...Object.keys(item)].some(key=>quoteKeys.has(key)))return false;
    return item.reason_code===undefined||reasonCodes.has(item.reason_code);
  }
  if(!supportedProfile)return false;
  if(item.reason_code!==undefined||item.parse_complete!==true||
    !(item.quote_age_seconds===null||(typeof item.quote_age_seconds==='number'&&Number.isFinite(item.quote_age_seconds)&&item.quote_age_seconds>=0))||
    !(item.observed_currency===null||/^[A-Z]{3}$/.test(item.observed_currency))||
    !(item.observed_adults===null||(Number.isInteger(item.observed_adults)&&item.observed_adults>=1&&item.observed_adults<=9))||
    !(item.observed_cabin===null||['economy','premium_economy','business','first'].includes(item.observed_cabin))||
    !(item.observed_direct_only===null||typeof item.observed_direct_only==='boolean')||
    !['resolved_safe','unresolved','unsafe'].includes(item.link_resolution)||
    !(item.displayed_price_twd===null||(Number.isInteger(item.displayed_price_twd)&&item.displayed_price_twd>0))||
    !(item.handoff_price_twd===null||(Number.isInteger(item.handoff_price_twd)&&item.handoff_price_twd>0))||
    !(item.handoff_checked_at===null||validTime(item.handoff_checked_at)))return false;
  if((item.handoff_price_twd===null)!==(item.handoff_checked_at===null))return false;
  if(item.handoff_price_twd!==null&&(item.displayed_price_twd===null||item.link_resolution!=='resolved_safe'))return false;
  return true;
}

function percentile(values,p){
  if(!values.length)return null;
  const sorted=[...values].sort((a,b)=>a-b);
  return sorted[Math.ceil(p*sorted.length)-1];
}
function rate(numerator,denominator){return denominator?numerator/denominator:null;}
function matches(observation,key,expected){
  return observation[key]!==null&&observation[key]!==undefined&&observation[key]===expected;
}

export function evaluateCalibration(observations,{authorized=false,terms_allowed=false,budget_approved=false,evaluated_at=new Date().toISOString()}={}){
  const base={schema_version:1,protocol_version:PROTOCOL_VERSION,provider:PROVIDER,provider_version:PROVIDER_VERSION,
    decision:'BLOCK',measured_at:null,expires_at:null,allowed_routes:[],route_metrics:{},blockers:[],
    approvals:{owner_authorized:authorized===true,terms_allowed:terms_allowed===true,budget_approved:budget_approved===true}};
  const blocker=reason=>({...base,blockers:[reason]});
  if(authorized!==true)return blocker('authorization_missing');
  if(terms_allowed!==true)return blocker('terms_unclear');
  if(budget_approved!==true)return blocker('budget_unapproved');
  if(!validTime(evaluated_at)||!Array.isArray(observations)||observations.length<1||observations.length>48||
    observations.some(item=>!validateObservation(item)))return blocker('invalid_or_unredacted_observation');
  if(observations.some(item=>hardStopOutcomes.has(item.outcome)||item.link_resolution==='unsafe'))return blocker('stop_rule_triggered');
  const grouped=new Map();
  for(const item of observations){
    if(!grouped.has(item.route))grouped.set(item.route,[]);
    grouped.get(item.route).push(item);
  }
  if([...grouped.values()].some(items=>items.length>DATE_WINDOWS.length||
    new Set(items.map(dateWindowDays)).size!==items.length))return blocker('sample_budget_exceeded');
  const metrics={};
  for(const [route,items] of grouped){
    const successes=items.filter(item=>item.outcome==='SUCCESS');
    const comparable=successes.filter(item=>item.handoff_price_twd!==null);
    const quoteAges=successes.map(item=>item.quote_age_seconds).filter(value=>value!==null);
    const comparisons=comparable.map(item=>Math.abs(item.handoff_price_twd-item.displayed_price_twd)/item.displayed_price_twd*100);
    const parsedDenominator=successes.length+items.filter(item=>item.outcome==='PARSE_FAILED').length;
    const profile=items[0].profile;
    const matchesCurrency=successes.filter(item=>matches(item,'observed_currency','TWD')).length;
    const matchesPassengers=successes.filter(item=>matches(item,'observed_adults',profile.adults)).length;
    const matchesCabin=successes.filter(item=>matches(item,'observed_cabin',profile.cabin)).length;
    const matchesDirectness=successes.filter(item=>matches(item,'observed_direct_only',profile.direct_only)).length;
    const safeLinks=successes.filter(item=>item.link_resolution==='resolved_safe').length;
    metrics[route]={
      attempted:items.length,successful:successes.length,parse_complete:successes.length,
      parse_sample_count:parsedDenominator,
      date_windows:[...new Set(items.map(dateWindowDays))].sort((a,b)=>a-b),
      quote_age_sample_count:quoteAges.length,
      currency_match_count:matchesCurrency,passenger_match_count:matchesPassengers,cabin_match_count:matchesCabin,
      directness_match_count:matchesDirectness,safe_link_resolved_count:safeLinks,
      search_success_rate:rate(successes.length,items.length),
      parse_completeness_rate:rate(successes.length,parsedDenominator),
      quote_age_p95_seconds:percentile(quoteAges,.95),
      currency_consistency_rate:rate(matchesCurrency,successes.length),
      passenger_consistency_rate:rate(matchesPassengers,successes.length),
      cabin_consistency_rate:rate(matchesCabin,successes.length),
      directness_consistency_rate:rate(matchesDirectness,successes.length),
      safe_link_resolution_rate:rate(safeLinks,successes.length),
      handoff_comparison_count:comparable.length,
      price_discrepancy_p95_percent:percentile(comparisons,.95),
    };
  }
  const allowed=ROUTE_KEYS.filter(route=>metrics[route]&&routeMetricPass(metrics[route]));
  if(!allowed.length)return {...base,route_metrics:metrics,blockers:['no_route_meets_predeclared_thresholds']};
  const decision=allowed.length===ROUTE_KEYS.length?'BUILD':'NARROW';
  const measuredAt=new Date(Date.parse(evaluated_at)).toISOString();
  return {...base,decision,measured_at:measuredAt,
    expires_at:new Date(Date.parse(measuredAt)+THRESHOLDS.maximumReceiptAgeMs).toISOString(),
    allowed_routes:allowed,route_metrics:metrics,blockers:[]};
}

export function collectorAdmission(env,now=Date.now()){
  if(env.COLLECTOR_ENABLED!=='true')return {admitted:false,state:'disabled',reason:'collector_disabled',
    decision:inspectAdmission(env.CALIBRATION_ADMISSION,now).decision,allowed_routes:[]};
  return inspectAdmission(env.CALIBRATION_ADMISSION,now);
}
