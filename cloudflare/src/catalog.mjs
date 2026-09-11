// Catalogue copied from config/routes.py at repository commit 0798ce9.
// Configured monitoring targets, NOT an assertion that a direct route is sold.
const a = (code,name,city,country,is_downtown=false) => ({code,name,city,country,is_downtown});
export const origins = [
  a('TPE','桃園國際機場','台北','台灣'), a('TSA','台北松山機場','台北','台灣',true),
  a('KHH','高雄小港機場','高雄','台灣'), a('RMQ','台中國際機場','台中','台灣'),
];
export const destinations = [
  a('NRT','成田國際機場','東京','日本'), a('HND','羽田機場','東京','日本',true),
  a('KIX','關西國際機場','大阪','日本'), a('FUK','福岡機場','福岡','日本',true),
  a('KMJ','阿蘇熊本機場','熊本','日本'), a('KOJ','鹿兒島機場','鹿兒島','日本'),
  a('OKA','那霸機場','沖繩','日本'), a('NGO','中部國際機場','名古屋','日本'),
  a('CTS','新千歲機場','札幌','日本'), a('SDJ','仙台機場','仙台','日本'),
  a('OKJ','岡山機場','岡山','日本'), a('TAK','高松機場','高松','日本'),
];
export const routes = [
  ['TPE','NRT'],['TPE','KIX'],['TPE','FUK'],['TPE','OKA'],['TPE','CTS'],['TPE','NGO'],
  ['TSA','HND'],['KHH','NRT'],['KHH','KIX'],['KHH','FUK'],['KHH','OKA'],['TPE','KMJ'],
  ['TPE','KOJ'],['TPE','SDJ'],['TPE','OKJ'],['TPE','TAK'],
].map(([origin,destination])=>({origin,destination}));
export const APP_ID='reese-max/ai-flight-radar:cloudflare-v1';
