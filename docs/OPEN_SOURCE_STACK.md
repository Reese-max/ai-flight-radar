# 已知開源專案與工具：目的、採用狀態及限制

本文件將「已整合的執行依賴」、「候選工具」與「商業服務」分開。列出某工具不代表已經接通，MCP 也不等於獨立票源。

## 已使用

| 專案／工具 | 本專案目的 | 實際位置 | 限制／授權注意 |
|---|---|---|---|
| [fast-flights](https://github.com/AWeirdDev/flights) | 建立 Google Flights 查詢及解析報價 | `providers/fast_flights_impl.py` | MIT；非 Google 官方公開 API，可能改版或限流。固定使用已發布的3.1.0介面 |
| [FastAPI](https://github.com/fastapi/fastapi) | 儀表板與 REST API | `api/app.py` | MIT；框架不會自動替產品完成認證或限流 |
| [SQLModel](https://github.com/fastapi/sqlmodel) | 結構化資料模型、SQLite 查詢及持久化 | `core/models.py`、`core/snapshots.py` | MIT；遷移與比較邏輯仍由本專案負責 |
| [SQLite](https://www.sqlite.org/) | 本機歷史快照、任務與通知記錄 | `core/database.py` | 本機原型先採單機資料庫，並非已完成分散式高可用 |
| [ntfy](https://github.com/binwiederhier/ntfy) | 發送手機／瀏覽器推播 | `notifier/ntfy_client.py` | 可自行架設；託管服務的配額及 topic 權限與程式授權是兩回事 |
| [pytest](https://github.com/pytest-dev/pytest) | 回歸測試與 mock 邊界 | `tests/` | MIT；測試不呼叫真實訂票或通知服務 |

Telegram 是可選的 Bot API 通知服務，不是這個 Python 程式直接內嵌的開源推播伺服器。GitHub Actions 是託管測試執行環境，不能因 workflow 可公開就把服務本身視為免費無限制的開源執行資源。

## 候選工具：未安裝、未啟用

| 工具 | 規劃目的 | 何時值得加入 | 為何現在不一起裝 |
|---|---|---|---|
| [Microsoft Playwright](https://github.com/microsoft/playwright) | 在允許自動化的來源操作瀏覽器，或做前端端到端測試 | API 無法提供必要資訊，且有可行的存取授權與維護預算時 | 瀏覽器成本較高；不能拿來繞過 CAPTCHA 或存取限制 |
| [Crawlee](https://github.com/apify/crawlee) | 管理多個已獲准的網站收集工作、佇列及重試 | 增加多個網站來源之後 | MVP 已有自己的搜尋排程，現在加入會重疊 |
| [Apprise](https://github.com/caronc/apprise) | 統一多通知渠道介面 | 需要 Email、Discord 等多種管道時 | 先修正送達狀態，再抽換發送介面；不能用新套件掩蓋漏報 |
| [PostgreSQL](https://www.postgresql.org/) | 多使用者及多 worker 的正式資料層 | SQLite 寫入競爭與操作規模真的成為瓶頸時 | 目前的租約 SQL 使用 SQLite dialect，切換時須一併改寫並測試 |
| [n8n](https://github.com/n8n-io/n8n) | 視覺化串接摘要、通知或人工核准工作流 | 非開發者需要維護外部流程時 | 原始碼可見但主要為 Sustainable Use License 等授權，不應直接列作 MIT/Apache 類自由開源依賴 |

[Huginn](https://github.com/huginn/huginn) 可作為事件式網頁監控架構的研究對象；[Apache Airflow](https://github.com/apache/airflow) 可作為大規模批次資料管線候選。兩者目前都不是執行依賴，也沒有必要與現有 loop 同時排程同一批任務。

## MCP 與第二票源

先前討論的 Google Flights MCP、Fli、All Flights MCP 適合研究工具介面與多供應商協調，但導入前必須逐一驗證特定版本、授權、測試及實際來源。**兩個 MCP 都查 Google Flights，仍然只有同一底層票源，不能算獨立交叉驗證。**本次不將尚未驗收的 MCP 加入 requirements。

[Duffel](https://duffel.com/docs) 屬航空商業 API 服務，不是免費開源票價資料庫。SDK 的授權不代表服務、查價、Offer 驗證或出票免費，也不能保證重現 Google Flights 上每一個 OTA 優惠。加入第二來源前，先確認可用市場、商業權限、計費及相同行程對應方法。

## 採用原則

先修正價格證據及通知送達，再增加工具。新增資料來源需要獨立 adapter、資料身分、費用界線、限流及故障測試；不要把更換 wrapper 誤當成增加市場覆蓋。採用任何來源前查閱其當下條款；遇到存取拒絕時停止或採用正式授權方式，不設計繞過措施。

參考核對日期：2026-09-11。候選清單是架構規劃，不是所有工具的整合完成清單；部署前仍須再次檢查各版本 LICENSE 與服務條款。本次未替此儲存庫新增專案授權。
