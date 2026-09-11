/** Pure display helpers. Price values always come from server observations. */
export function taipeiDate(now = new Date()) {
  return new Intl.DateTimeFormat('en-CA', {timeZone:'Asia/Taipei', year:'numeric', month:'2-digit', day:'2-digit'}).format(now);
}
export function addDays(iso, days) {
  const d = new Date(`${iso}T12:00:00Z`); d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0,10);
}
export function money(value) {
  return Number.isFinite(value) && value > 0 ? `NT$${Math.round(value).toLocaleString('en-US')}` : '價格未知';
}
export function isStale(q, now = Date.now()) {
  const timestamp = Date.parse(q.searched_at);
  return q.expired === true || !Number.isFinite(timestamp) || now - timestamp > 6*3600000 || timestamp-now > 300000;
}
export function relativeTime(iso, now = Date.now()) {
  const stamp = Date.parse(iso);
  if (!Number.isFinite(stamp) || stamp-now > 300000) return '時間未知';
  const mins = Math.max(0, Math.floor((now-stamp)/60000));
  return mins < 1 ? '剛剛更新' : mins < 60 ? `${mins} 分鐘前更新` : mins < 1440 ? `${Math.floor(mins/60)} 小時前更新` : `${Math.floor(mins/1440)} 天前更新`;
}
export function sourceURL(q) {
  try {
    const u = new URL(q.source_url);
    if (u.origin === 'https://www.google.com' && u.pathname === '/travel/flights' && !u.username && !u.password) return u.href;
  } catch {}
  return null;
}
export function hasBaseline(q) {
  return q.baseline_confident === true && q.history_truncated !== true && Number(q.prior_observed_days) >= 5 && Number.isFinite(q.baseline_twd) && q.baseline_twd > 0 && Number.isFinite(q.drop_pct);
}
export function filteredQuotes(quotes, mode, confidentOnly, sort, destinations = []) {
  let rows = quotes.filter(q => Number.isFinite(q.price_twd) && q.price_twd > 0);
  if (confidentOnly) rows = rows.filter(hasBaseline);
  if (mode === 'weekend' || mode === 'leave') rows = rows.filter(q => {
    const dep = new Date(`${q.depart_date}T12:00:00Z`), ret = new Date(`${q.return_date}T12:00:00Z`);
    const days = Math.round((ret-dep)/86400000);
    if (!Number.isInteger(days) || days < 1 || days > 4) return false;
    if (mode === 'weekend') return [5,6].includes(dep.getUTCDay()) && [0,1].includes(ret.getUTCDay());
    let weekdays = 0;
    for (let i=0;i<=days;i++) if (![0,6].includes((dep.getUTCDay()+i)%7)) weekdays++;
    return weekdays <= 1; // Conservative: no invented holiday or working-hour assumptions.
  });
  rows.sort((a,b) => sort === 'recent' ? Date.parse(b.searched_at)-Date.parse(a.searched_at) :
    sort === 'price' ? a.price_twd-b.price_twd : (Number(hasBaseline(b))-Number(hasBaseline(a))) ||
      ((hasBaseline(b) ? b.drop_pct : 0)-(hasBaseline(a) ? a.drop_pct : 0)) || a.price_twd-b.price_twd);
  if (mode === 'cities') {
    const seen = new Set();
    rows = rows.filter(q => {const city = destinations.find(a=>a.code===q.destination)?.city || q.destination;
      if(seen.has(city)) return false; seen.add(city); return true;});
  }
  return rows;
}
export function cleanWatches(value) {
  if (!Array.isArray(value)) return [];
  return value.slice(0,100).filter(w=>w && typeof w.id==='string' && w.id.length <= 64 && typeof w.name==='string' &&
    /^[A-Z]{3}\/[A-Z]{3}$/.test(w.route) && Number.isInteger(w.budget) && w.budget>0 && w.budget<=1000000)
    .map(w=>({id:w.id, name:w.name.slice(0,60), route:w.route, budget:w.budget, enabled:w.enabled !== false}));
}
