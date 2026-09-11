# Cloudflare Workers + D1 部署

本模組把既有 Figma UI 接到 JavaScript Worker 與 D1。原 `web/`、FastAPI、SQLite、Docker 與查價演算法仍保留。Python `FastFlightsProvider` 由獨立的限量批次呼叫，不在 Workers 裡啟動 Python 子程序。

**提交程式、通過 CI、正式部署是不同狀態。必須有部署紀錄和 HTTPS 驗收才可稱為已上線。** 本文件不預填帳號、資料庫 UUID、秘密或公開網址。

## 已提供的工作流程

| Workflow | 作用 | 是否發布 |
|---|---|---|
| `Cloudflare Workers checks` | 離線測試、實際 UI 建置、Wrangler bundle、local D1 migration、workerd HTTP 檢查 | 不發布，不呼叫航空來源 |
| `Deploy Cloudflare Workers` | 手動確認目標、檢查設定、驗證指定 D1 名稱、遠端 migration、發布 Worker、設定應用秘密、HTTP 驗收 | 只有 main 的手動執行且確認 `ai-flight-radar-cf` 才發布 |
| `cloudflare/templates/cloudflare-collector.yml` | 最多三個查價任務的範本 | 尚未啟用，沒有運作中的排程 |

檢查流程的 prerequisites job 只報告缺少或格式不合的**設定名稱**，不輸出憑證內容，也不向 Cloudflare 送請求。`ready=true` 只代表設定齊全，不代表帳號授權已通過。

## 正式發布前需要的設定

先建立專用 D1，名稱必須為 `ai-flight-radar-cf`，不要使用其他專案的資料庫。帳號授權不足時停止，不改用其他帳號或資料庫。此版本的自動發布流程不建立 D1、購買網域或升級付費方案。

在本儲存庫的 GitHub Actions 設定提供：

| 名稱 | 類型 | 目的 |
|---|---|---|
| `CLOUDFLARE_API_TOKEN` | Secret | 限指定帳號的 Workers Scripts Edit、D1 Edit，部署程式使用 |
| `CLOUDFLARE_ACCOUNT_ID` | Variable 或 Secret | 指定部署帳號 |
| `CF_RADAR_DATABASE_ID` | Variable 或 Secret | 專用 `ai-flight-radar-cf` 的真實 D1 UUID |
| `CF_RADAR_ADMIN_KEY` | Secret | 應用管理員金鑰，32–256 字元，不是 Cloudflare Token |
| `CF_RADAR_COLLECTOR_KEY` | Secret | 查價收集器專用金鑰，32–256 字元，必須不同於管理員金鑰 |

秘密只放平台的 Secret 設定，不貼到對話、Issue、程式碼、URL 或測試報告。前端只在分頁記憶體保留管理員输入，不公開 collector 或 Cloudflare token。

設定完成後，在 Actions 選 `Deploy Cloudflare Workers`，使用 main，確認欄輸入 `ai-flight-radar-cf`。流程會以固定的 Worker 名稱及檢查過的 D1 ID 部署；先發布程式時未配置金鑰的寫入會拒絕，之後將兩個專用金鑰同步到同一個 Worker。任何步驟失敗即停止，可能已完成前面的 migration 或發布，不能把失敗概括為完全沒有改動。

成功網址取自 Wrangler 真實輸出，不由程式猜帳號子網域。驗收包含首頁、app.js、API 身分、真實資料契約、未授權 POST 回應 401。這不代表已成功取得航空報價。最初 `COLLECTOR_ENABLED=false`，通知未整合，資料庫空白時頁面不顯示示範票價。

## 本機驗證

需 Node.js 22.13+、Python 3.12+：

```bash
node --test cloudflare/tests/*.test.mjs
python -m unittest discover -s cloudflare/tests -p 'test_*.py' -v
python cloudflare/scripts/collector.py
cd cloudflare
npm install
npm run build
npm run wrangler-check
npx --no-install wrangler d1 migrations apply DB --local
npx --no-install wrangler dev
```

前兩項測試用 SQLite 作 D1 介面替身；`wrangler dev` 才是實際 workerd/local D1。`collector.py` 沒有 `--execute` 就是零網路呼叫的 dry-run。npm 所產生的 package-lock 應保留並審閱；不要手寫假的鎖檔。正式憑證不應提供给套件安裝或離線測試。

## 價格與排程邊界

同一航線、出回程日期、幣別、成人數、艙等、直飛条件與來源才可共用歷史。每次查價一筆最低報價，先排除本次觀測，再按觀測日中位數等權平均。至少五個先前觀測日才顯示折扣；讀取歷史超過有界數量時不宣稱可靠折扣。此版本不宣稱 90 日新低。

探索顯示每個查詢的**最新**快照，先選最新再篩預算，不回退成舊便宜價；六小時過期後不列為有效報價。日期比較保留各日期的最新觀測並標示過期，不冒充觀測時間序列。行李、完整往返航段與最終價格仍須來源確認。

收集器每批最多 3 個任務、每個來源子程序 90 秒逾時；伺服器預設每小時最多 3 次認領。來源失敗就結束剩餘批次，不執行自動重試或繞過驗證。任務租約 15 分鐘，重送去重、過期擁有者不能覆寫新結果。查無結果與來源錯誤不寫零元快照。

上線並驗證來源後，才另外啟用 collector 範本、設定 GitHub `CF_RADAR_URL`、`CF_RADAR_COLLECTOR_KEY` 和雙邊 enable flag。GitHub 排程不是準點服務，需監控最近成功快照。此初始發布流程每次都保持 collector 關閉；開始正式排程後，要先調整並審閱發布設定，避免更新時意外停用。

任務最多 128、快照最多 20,000、收據最多 100,000；到上限停止新增，不自動刪價格歷史。這些是程式保護，不等於保證帳單為零。免費 CPU、D1 每日讀寫和儲存配額須以實際平台用量驗證。先從少量固定日期收集，不窮舉全年所有航點。

追蹤清單仍限目前瀏覽器，不跨裝置、不建立私人雲端規則、不直接推播。缺少真實資料時維持空狀態。

## 官方文件

- [Workers Static Assets](https://developers.cloudflare.com/workers/static-assets/)
- [D1 migrations](https://developers.cloudflare.com/d1/wrangler-commands/)
- [Workers Secrets](https://developers.cloudflare.com/workers/configuration/secrets/)
- [Cloudflare GitHub Action](https://github.com/cloudflare/wrangler-action)
