# 上線部署與操作

本專案現在包含可執行的 Figma UI 2.0、FastAPI API 與 Docker 啟動器。**提交程式、CI 成功與建立公開網址是三件不同的事；沒有成功的雲端部署紀錄及 HTTP 驗收，不應標示「已上線」。**

## 部署模型

採單一服務、單一副本：瀏覽器 → HTTPS → Uvicorn/FastAPI → SQLite 持久卷。可選的 scanner 與 Web 程序由 `deploy/start.py` 管理，共用同一資料庫。不把 SQLite 放在兩個獨立服務的暫存磁碟，也不複製檔案充當跨服務同步。

`AUTOSCAN_ENABLED=false` 為預設。初次啟動的空白資料庫會顯示沒有查價紀錄，不會顯示 Figma 示範票價。啟用 scanner 後逐次累積真實快照，五個先前觀測日之前不產生歷史折扣。網站重新整理只讀資料，不會增加即時查價。

## Railway 部署設定

連接已授權的 Railway 帳號後，為 `Reese-max/ai-flight-radar` 的 `main` 建立**一個**服務，使用根目錄 `Dockerfile`。先確認平台顯示的運算及儲存費用，沒有另行核准不要升級方案。

| 設定 | 值 |
| --- | --- |
| Source | GitHub `Reese-max/ai-flight-radar`, branch `main` |
| Builder | 根目錄 Dockerfile 自動偵測 |
| Start command | 使用 Docker CMD：`python deploy/start.py` |
| Persistent Volume mount | `/app/data` |
| `DB_PATH` | `/app/data/flights.db` |
| `DEPLOYMENT_MODE` | `public` |
| `API_KEY` | 至少 32 字元的隨機秘密，存在平台 Secrets/Variables，不寫入 GitHub |
| `RAILWAY_RUN_UID` | `0`，僅讓啟動器準備 root 掛載的資料卷，隨後降權至 uid 10001 |
| `AUTOSCAN_ENABLED` | 首次驗收先 `false`；確認來源使用條件及預算後設 `true` |
| `SCAN_BATCH_SIZE` | `3`，允許 1–10 |
| `SCAN_INTERVAL_SECONDS` | `300`，允許 60–86400；每批結束後再等候 |
| `SCAN_TIMEOUT_SECONDS` | `180`，允許 30–600 |
| Healthcheck path | `/api/health`，timeout 120 秒 |
| Restart policy | On failure，最多重試 3 次 |
| Replicas | `1` |
| Public networking | 產生平台 HTTPS 網域；使用平台提供的 `PORT` |

掛載必須在第一次啟動前完成。Railway 存在但沒有 `RAILWAY_VOLUME_MOUNT_PATH` 時，啟動器會拒絕啟動，以免誤把歷史資料寫入暫存磁碟。此變數由 Railway 掛載 Volume 後自動提供，不要自行偽造它。啟動器只調整設定資料目錄及既有 DB/日誌/心跳檔的擁有者，不遞迴更改其他檔案，不刪除資料。

本次以 Dockerfile 與平台服務設定為準，不以新增 `railway.json` 代替持久卷、公開網域與帳號授權。服務建立與部署成功需要額外的實際平台操作。

官方依據：[Dockerfile 偵測](https://docs.railway.com/builds/dockerfiles)、[Volume 掛載與權限](https://docs.railway.com/volumes)、[公開部署驗收](https://docs.railway.com/guides/docker-compose)。

## 必須完成的上線驗收

HTTPS 首頁及 `/assets/app.js` 均能載入，`/api/health` 回應成功。`/api/ui/config` 只能回傳布林設定與觀測狀態，不得包含 API Key、Bot Token、Chat ID 或私人 topic。未授權 POST `/api/scan/trigger` 必須回應 401；缺少公網管理金鑰時服務應拒絕啟動。

重新啟動後，資料庫內容必須仍存在。再啟用 scanner，確認程序心跳更新，並**另外確認**資料庫出現新的成功查價快照。沒有快照時不可把「程序運作中」說成「已成功抓票」。六小時前的報價不在探索列表作有效報價，但日期比較可保留並標為過期。測試過期、沒有資料、來源失敗、手機瀏覽及管理金鑰清除。

`/api/health` 只代表 API/DB 健康，不代表航空資料供應商正常；平台上線健康檢查也不是持續 uptime 保證。部署／回滾使用同一 Volume，安排維護時間並保留備份。

## 本機 Docker 驗收

在專案根目錄產生隨機 API Key，存入未追蹤的 `.env`，再執行：

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
# 將結果設成 .env 的 API_KEY，不要提交或公開分享。
docker compose up --build -d
# http://127.0.0.1:8787
```

Compose 預設只開放本機，不對公網裸露 HTTP。公開服務使用 HTTPS 反向代理。Docker 現在預設公網保護，因此舊版沒有 API_KEY 的 `docker run` 範例不再適用。

## 通知與追蹤的界線

瀏覽器追蹤清單目前使用 localStorage，只儲存名稱、航線、目標預算與啟用狀態。**不會建立伺服器排程、不會跨裝置同步，也不會新增個人推播**。管理員可用原有 ntfy/Telegram 系統對原有 Deal 規則發送通知。

`NTFY_ENABLED`、`TELEGRAM_ENABLED` 預設皆 false。不要共用公開示範 topic；保護通知端點、設定自己的憑證，並在啟用前確認接收對象。金鑰僅輸入網站設定頁的本次分頁記憶體，不放 URL 或永久瀏覽器儲存。

## 維運限制

目前仍是一個 Google Flights 非官方取得器，不保證來源覆蓋或長期可用；遇到限制應降低頻率、停止查詢或改用合約資料來源，不迴避限制。全域限速只涵蓋單一 Web 程序的手動查價；前方仍需平台層的流量保護。公開讀取 API 有筆數、歷史資料量與 body 大小上限，但尚不是多租戶 SaaS。需要多副本、私人雲端追蹤與更高資料量時，先遷移 PostgreSQL、身分認證、全域工作佇列及配額管理。

每次更新會執行原有測試、新 UI/API 測試、瀏覽器模擬及 Docker 煙霧測試。這些測試不用真實票價、不送通知、不購票；雲端實際抓價與域名驗收仍是獨立步驟。
