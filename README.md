# AI Flight Radar

台灣出發的機票報價搜尋、歷史觀測與低價提醒原型。核心原則是：**先確定比較方式正確，再宣稱發現便宜票。**

目前使用 `fast-flights 3.1.0` 取得 Google Flights 搜尋結果、SQLite/SQLModel 保存資料、FastAPI 提供既有網頁介面，以及 ntfy/Telegram 發送選擇性通知。只有一個實際機票資料來源；NLP 與摘要目前是規則式程式，不是已接上大型語言模型的自主 Agent。

## 安裝與啟動

建議 Python 3.12。以下指令在儲存庫根目錄執行：

```bash
python -m venv .venv
# Linux / macOS / WSL
source .venv/bin/activate
# Windows PowerShell 改用：.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
cp .env.example .env
# Windows PowerShell：Copy-Item .env.example .env
python main.py init
python main.py status
python main.py scan --count 3
python main.py server
```

瀏覽 `http://127.0.0.1:8787`。需要持續追蹤時，在另一個終端機執行 `python main.py loop`；啟動網頁伺服器**不等於**已啟動持續掃描。WSL/Linux 也能使用 `./run-radar.sh init|status|scan|loop|server`。

`scan --count 3` 最多處理三個可執行任務；沒有到期任務就結束，不會為湊足次數無限等待。外部搜尋仍需要可用網路，並可能因來源改版、限流或查無航班失敗。

## 這次的價格可信度修正

每次成功搜尋保留所有原始 offer，但只新增**一筆最低價快照**作為統計輸入。相同航線、出發日、回程日、幣別、旅客數、艙等、直飛條件與來源才會共用比較基準。先在每天內取快照中位數，再以觀測日等權平均，避免高頻追蹤某一天改變其統計權重。

本批價格不加入自己的比較基準。近 30 日內不足五個不同觀測日，不產生歷史降幅優惠；空白歷史不再填入人工預設的「市場均價」。`90D_LOW` 另要求長期間及足夠觀測日，不能靠幾筆資料宣稱 90 日新低。30/90 日重疊窗口不再重複加分。

行李、附加費與完整往返航段未經確認，不能由航空公司名稱推定含托運。未知時間不加分。分數仍以 100 為名目上限，但未驗證的行李部分保留 5 分、不送分，因此目前最高 95 分。

完整定義及限制見 [價格判斷方法](docs/PRICE_INTELLIGENCE.md)。

## 舊版升級

先停止舊 worker，備份 `data/flights.db`（自訂 `DB_PATH` 則備份該檔案），更新程式與依賴，再執行 `python main.py init`。

升級只新增 `search_snapshots`、`task_leases`、`radar_migrations` 三張表，不刪除原始查價或成功通知歷史。首次升級會把舊算法的 active deals 標為 expired、清空舊統計摘要，要求新方法重新產生證據；不會重複清空後續產生的新優惠。**舊 offer 不會冒充新方法收集到的快照，需重新累積觀測日。**

## 通知與安全

ntfy 預設關閉。請在 `.env` 設定自己的 topic，再明確設定 `NTFY_ENABLED=true`；不要共用舊示範 topic。難猜的 topic 名稱不等於存取控制，私人通知應使用受保護／保留的 topic 或自行架設有權限設定的服務。

Telegram 需設定 `TELEGRAM_ENABLED=true`、`TELEGRAM_BOT_TOKEN` 與 `TELEGRAM_CHAT_ID`。`.env`、資料庫及金鑰檔不應推送到 GitHub。

兩個通知渠道都失敗時，不會標記為已通知；至少一個成功才啟動既有冷卻規則。部分渠道失敗的獨立重試仍列在後續工作。

API 預設只監聽本機。設定 `API_KEY` 後，手動觸發掃描 API 需要 `X-API-Key` header。既有網頁尚無 API key 輸入介面；設定金鑰後，應以授權 API 客戶端觸發，或由可信反向代理處理。對外服務前還需 HTTPS、認證、全域限流及前端安全檢查，不能把這個本機原型直接視為公開 SaaS。

## 排程與有效期

四層追蹤間隔維持 6 小時／2 小時／1 小時／30 分鐘；加入每任務 15 分鐘租約，防止同一任務被兩個程序同時處理。失敗至少延遲 10 分鐘再嘗試。租約不是無限長鎖；超長請求及多 worker 全域流量預算仍需後續補強，目前建議一個持續掃描 worker。

報價最長顯示 6 小時，超時或出發日期已過不再列為有效優惠。這是資料新鮮度規則，不是保證六小時內仍可購買。預設是抽樣掃描，不是窮舉日本所有航線與日期。

## 測試

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m compileall -q ai api config core engine notifier providers main.py
```

測試使用獨立臨時 SQLite、假的報價與假的通知回傳，不會發送真實通知、下單或用真實票價作固定斷言。CI 檢查依賴、語法、統計、資料庫、通知狀態、API 與 `fast-flights` v3 呼叫介面；不代表 Google Flights 線上抓取永遠可用。

## Docker（選用）

```bash
docker build -t ai-flight-radar .
docker run --rm -p 127.0.0.1:8787:8787 -v radar-data:/app/data ai-flight-radar
```

此命令只啟動本機可存取的網頁服務，不自動啟用通知或掃描。映像提供建置定義；請在部署環境自行確認 Docker 建置及網路條件。

## 文件

- [已知開源專案與工具：用途、採用狀態、限制](docs/OPEN_SOURCE_STACK.md)
- [價格快照、統計與升級設計](docs/PRICE_INTELLIGENCE.md)
- [後續路線圖與驗收標準](docs/ROADMAP.md)

原儲存庫尚未提供專案 LICENSE；此次不代替作者決定授權。公開可讀不代表可以忽略授權，引用相依專案仍需遵守各自條款。
