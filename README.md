# AI Flight Radar

台灣出發的機票報價觀測工作台。**先確定比較方式正確，再宣稱發現便宜票。**

Figma UI 2.0 已實作為響應式網頁：桌面與手機導覽、報價篩選、日期比較、票價詳情、瀏覽器追蹤清單，以及管理員查價設定。FastAPI/SQLite 後端保留原有價格快照與通知規則。程式可使用 Docker 部署；**儲存庫有部署設定不代表已建立公開網站，正式上線需要雲端服務、持久卷及 HTTPS 網域驗收。**

## 安裝與本機啟動

建議 Python 3.12，在儲存庫根目錄執行：

```bash
python -m venv .venv
source .venv/bin/activate
# Windows PowerShell：.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
cp .env.example .env
# Windows PowerShell：Copy-Item .env.example .env
python main.py init
python main.py status
python main.py scan --count 3
python main.py server
```

瀏覽 `http://127.0.0.1:8787`。本機需要持續掃描時，在另一個終端機執行 `python main.py loop`。WSL/Linux 可用 `./run-radar.sh init|status|scan|loop|server`。網頁重新整理與自然語言搜尋只讀取已觀測資料，不自動掃描航空來源。

`scan --count 3` 最多處理三個可執行任務；沒有到期任務就結束。來源可能因改版、限流、網路問題或沒有結果而失敗。首次啟動沒有報價時，不以示範機票填滿頁面。

## 網站功能與實作邊界

| 功能 | 實際行為 |
| --- | --- |
| 探索低價 | 顯示每組查詢的最新真實快照，再套用預算與有效期 |
| 日期比較 | 不同出發／回程日期組合的報價，不是假裝成時間序列 |
| 票價詳情 | 顯示來源、觀測時間、歷史依據；行李與最終總價未知時明示 |
| 自然語言 | 既有規則解析，先由使用者核對條件，不是已接 LLM 的自主 Agent |
| 追蹤清單 | 儲存在目前瀏覽器，無跨裝置同步，不會建立伺服器排程或推播 |
| 手動查價 | 一次提交一個任務；公網模式限管理員金鑰及每分鐘一次 |
| 程序狀態 | 依真正心跳檔顯示；成功抓票需另外看到新資料庫快照 |

目前只有一個實際航空報價來源：`fast-flights 3.1.0` 取得 Google Flights 搜尋資料。多 Provider 與私人雲端追蹤仍在路線圖，不把計畫寫成已完成。

## 價格判斷

每次成功搜尋保存原始 offers，但統計只使用一筆最低價快照。相同航線、出發日、回程日、來源、幣別、旅客數、艙等及直飛條件才共用基準。每日先取快照中位數，再以觀測日等權平均；本批價格不加入自己的比較基準。

近 30 日不足五個不同先前觀測日，不產生歷史降幅。90 日新低另有覆蓋門檻，不能靠少量資料宣稱。人工預設市場均價已取消，未知時間不加分，不由航空公司名稱推定托運行李。報價最多作六小時有效觀測，不保證期間仍可買到。

詳見 [價格判斷方法](docs/PRICE_INTELLIGENCE.md)。

## Docker 與雲端

新增 `deploy/start.py`：同一服務管理 Web 與可選的 bounded scanner，共用持久化 SQLite。支援平台 `PORT`、啟動健康檢查、SIGTERM 關閉、有限批次與超時。公網部署缺少至少 32 字元的管理金鑰時拒絕啟動。

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
# 將結果寫入本機 .env 的 API_KEY，不提交 GitHub。
docker compose up --build -d
```

Compose 預設綁定本機，通知與自動掃描均關閉。Railway 使用根目錄 Dockerfile、`/app/data` 持久卷、單一副本及 HTTPS 網域；不能只部署靜態 HTML 就宣稱查價後端已上線。

完整設定、費用確認、Volume 權限及上線驗收見 [部署文件](docs/DEPLOYMENT.md)。

## 舊版升級與通知安全

先停止舊 worker，備份 `data/flights.db`（自訂 DB_PATH 則備份該檔案），再更新依賴並執行 `python main.py init`。原價格可信度升級只新增快照／租約／migration 表，保留原始查價與成功通知歷史。首次遷移會使舊算法的有效優惠過期並重建統計；舊 offers 不冒充新方法的快照。此 UI 更新不刪除既有價格資料。

ntfy 與 Telegram 預設關閉，需在伺服器環境變數明確啟用並設定自己的接收對象。不要共用公開示範 topic。兩個渠道都失敗時不標為已通知；個別渠道的獨立重試仍待補強。`.env`、資料庫與憑證不得推送 GitHub。

公網金鑰只在本次分頁記憶體使用，不放 URL 或永久瀏覽器儲存。API 不向前端提供 Bot Token、Chat ID 或私人 topic。對外服務仍需平台流量防护；目前不是完整多租戶 SaaS。

## 測試

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
node --test tests/test_ui_logic.mjs
# 選用瀏覽器測試：
python -m pip install playwright
python -m playwright install chromium
python tests/browser_smoke.py
```

CI 包含原有測試、UI/API 測試、Node 顯示邏輯、瀏覽器模擬與 Docker 建置／啟動檢查。測試使用臨時資料庫與合成 API 回應，不送真實通知、不購票，也不以模擬票價作為正式網站資料。通過 CI 不代表上游 Google Flights 永遠可用。

## 文件與設計

- [Figma 設計](https://www.figma.com/design/JPE9g17smfFB6R7eKxjRDr?node-id=6-2)
- [UI 實作、資產來源與功能邊界](docs/UI_IMPLEMENTATION.md)
- [部署與維運](docs/DEPLOYMENT.md)
- [已知開源專案與工具：目的、採用狀態、限制](docs/OPEN_SOURCE_STACK.md)
- [價格判斷方法](docs/PRICE_INTELLIGENCE.md)
- [後續路線圖](docs/ROADMAP.md)

原儲存庫尚未提供專案 LICENSE；本次不代替作者決定授權。公開可讀不等於可忽略授權，引用相依專案仍需遵守各自條款。
