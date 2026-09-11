/** Copy the existing UI; only adapt Cloudflare-specific status and help copy. */
import {readFile,writeFile,mkdir,readdir,copyFile,rm} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
export const STATIC_HEADERS=`/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: no-referrer
  X-Frame-Options: DENY
  Permissions-Policy: camera=(), microphone=(), geolocation=()
  Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'; object-src 'none'
`;
function replaceRequired(source,from,to){
  if(!source.includes(from))throw new Error(`Original UI changed; review adapter marker: ${from.slice(0,45)}`);
  return source.replaceAll(from,to);
}
export function adaptHTML(source){
  const replacements=[
    ['持續掃描程序','定時查價批次'],
    ['需要有效的程序心跳','依最近批次回報顯示，不代表持續執行'],
    ['觸發一次查價','排入下次查價'],
    ['指定航線，排入一次查價；不是全境掃描，也不會啟動常駐程序。','指定航線，加入下次已啟用的批次；不會立即查價，也不會啟動常駐程序。'],
    ['只有伺服器管理員可透過環境變數設定通知。','Cloudflare 版本尚未整合通知，瀏覽器追蹤清單不會觸發推播。'],
    ['/docs/DEPLOYMENT.md','/docs/CLOUDFLARE.md'],
    ['程序心跳只代表程序存在，成功查價必須有新快照。','批次回報不代表查價成功；成功查價必須另有新快照。'],
    ['每一列是不同日期組合的最低觀測價','每一列是不同日期組合的最新觀測价'.replace('价','價')],
  ];
  for(const [from,to]of replacements)source=replaceRequired(source,from,to);return source;
}
export function adaptJS(source){
  source=replaceRequired(source,"not_started:'尚未啟動'","not_started:'尚未啟動',batch_ok:'最近批次有報價',batch_empty:'最近批次無新報價',batch_error:'最近批次異常'");
  source=replaceRequired(source,"stale:'心跳逾期'","stale:'批次回報已逾期'");
  source=replaceRequired(source,'心跳：${relativeTime(cfg.worker.heartbeat_at)}','批次回報：${relativeTime(cfg.worker.heartbeat_at)}');
  source=replaceRequired(source,'尚無有效心跳','尚無有效批次回報');
  source=replaceRequired(source,'已提交一個任務；不代表已取得新報價，也未啟動持續掃描。',
    '已加入待查清單，等待下次批次；未啟用收集器時不會執行。');
  source=replaceRequired(source,"$('metricWorker').textContent=workerLabel(cfg.worker.status);",
    "$('metricWorker').textContent=cfg.worker.collector_enabled===false?'收集器關閉':workerLabel(cfg.worker.status);");
  return source;
}
export async function build(root=fileURLToPath(new URL('..',import.meta.url))){
  root=path.resolve(root);
  const from=path.join(root,'web'),output=path.join(root,'cloudflare','public');
  // Validate source compatibility before removing a previous generated build.
  const html=adaptHTML(await readFile(path.join(from,'index.html'),'utf8'));
  const js=adaptJS(await readFile(path.join(from,'assets/app.js'),'utf8'));
  async function copy(dir,to){
    await mkdir(to,{recursive:true});
    for(const entry of await readdir(dir,{withFileTypes:true})){
      if(entry.isSymbolicLink())throw new Error('UI assets must not contain symlinks');
      if(entry.isDirectory())await copy(path.join(dir,entry.name),path.join(to,entry.name));
      else if(/\.(css|js|mjs|svg|png|webp)$/.test(entry.name))await copyFile(path.join(dir,entry.name),path.join(to,entry.name));
    }
  }
  await rm(output,{recursive:true,force:true});await mkdir(output,{recursive:true});
  await copy(path.join(from,'assets'),path.join(output,'assets'));
  await writeFile(path.join(output,'index.html'),html);
  await writeFile(path.join(output,'assets/app.js'),js);
  await writeFile(path.join(output,'_headers'),STATIC_HEADERS);
  return output;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  console.log('Built UI at '+await build());
}
