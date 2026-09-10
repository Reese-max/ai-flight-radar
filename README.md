# AI Flight Radar (AI 自動低價機票搜尋、追蹤與旅遊情報雷達)

> **先找哪裡、哪一天出現異常便宜機票，再決定是否旅行。**
> 具備全天候自動排程、智慧分層掃描 (Progressive Tiered Queue)、Deal Score 評分模型與即時推播通知。

---

## 一、系統核心能力

1. **Google Flights 即時航線爬取 (`fast-flights`)**
   - 支援台灣主要機場 (`TPE`, `TSA`, `KHH`, `RMQ`) 至日本 12 大熱門目的地 (`NRT`, `HND`, `KIX`, `FUK`, `OKA`, `CTS`, `NGO`, `KMJ`, `KOJ`, `SDJ`, `OKJ`, `TAK`)。
   - 內建 RateLimiter 限流、隨機 Jitter (3~6s) 與指數退避 (Exponential Backoff)，兼顧效率與防封鎖。

2. **漸進式排程規劃器 (Progressive Search Planner)**
   - 避開暴力枚舉的排列組合爆炸，採用智慧採樣窗口 (未來 14~90 天，以 4~5 天行程為基準)。
   - 動態四階梯佇列 (Tiered Queue)：
     - **Tier 1 (標準監控)**：每 6 小時。
     - **Tier 2 (價格波動)**：降幅 > 10%，每 2 小時。
     - **Tier 3 (逼近神價)**：Deal Score ≥ 75 或降幅 > 20%，每 1 小時。
     - **Tier 4 (極致破盤)**：Deal Score ≥ 85 或降幅 > 35%，每 30 分鐘緊密追蹤座位餘量。

3. **Deal Score 智慧多維度評分 (0 ~ 100 分)**
   - **絕對價格競爭力 (0~25 分)**：超甜價位加分。
   - **相對 30 日均價降幅 (0~25 分)**：大降幅破盤加分。
   - **相對 90 日均價降幅 (0~15 分)**。
   - **歷史新低紀錄 (0~10 分)**。
   - **直飛航班 (10 分)**。
   - **日間航班時間友善度 (5 分)**：扣除紅眼/清晨 00:00~06:00 起飛班機。
   - **市區型便利機場 (5 分)**：羽田/松山/福岡加分。
   - **航空公司服務等級 (5 分)**：含全服務或標註廉航。

4. **主動警報與通知去重 (Alert Engine & Throttling)**
   - 整合 **ntfy** (免設定、一鍵訂閱推播至手機/瀏覽器)。
   - 整合 **Telegram Bot**。
   - 內建 12 小時冷卻狀態機與價格二次降幅閥值，避免同班神票重複洗版。

5. **AI 意圖探測與情報簡報 (NLP Intent & Deal Intelligence)**
   - 自然語言需求解析（例如：「幫我找未來半年台灣出發去日本，直飛，旅行 4～5 天，來回最好低於 8,000 元」）。
   - 每日情報報告：「今天去哪裡最值得買？」。

6. **即時視覺化儀表板 (Web Dashboard & REST API)**
   - FastAPI 後端 + Tailwind CSS 暗色系響應式儀表板。
   - 支援即時手動觸發單一航線掃描、查看歷史價格統計與點擊一鍵導向 Google Flights。

---

## 二、快速啟動指南

### 1. 目錄位置
```bash
cd /mnt/c/Users/Administrator/ai-flight-radar
```

### 2. 核心指令

| 指令 | 說明 |
| :--- | :--- |
| `./run-radar.sh status` | 顯示當前系統狀態總覽與今日高評分 Deals 榜單 |
| `./run-radar.sh scan --count 3` | 執行單次批次掃描（指定筆數） |
| `./run-radar.sh loop` | 啟動全天候自動雷達巡邏迴圈 (Progressive Loop) |
| `./run-radar.sh server` | 啟動 FastAPI Web 儀表板 (`http://localhost:8787`) |
| `./run-radar.sh nlp "查詢詞"` | 在 CLI 測試 AI 自然語言需求解析 |

---

## 三、Web 儀表板與推播設定

* **本機儀表板**：瀏覽器開啟 `http://localhost:8787`
* **手機即時推播訂閱 (ntfy)**：
  - 手機下載 [ntfy App](https://ntfy.sh)（iOS / Android）或使用瀏覽器打開：
  - 訂閱 Topic：`flight-radar-taiwan`
  - 一旦雷達發現 Deal Score ≥ 80 的機票，將立刻收到推播，點擊通知直接開啟 Google Flights 預訂頁！
* **Telegram Bot 推播 (可選)**：
  - 在 `config/settings.py` 或系統環境變數中設定 `TELEGRAM_BOT_TOKEN` 與 `TELEGRAM_CHAT_ID` 即可自動啟用。

---

## 四、資料庫與架構設計

* **SQLite 資料庫**：位於 `data/flights.db`
* **核心資料表**：
  - `routes`：監控航線基礎清單。
  - `flight_records`：每一次爬取的詳細航班價格、時間、航空公司記錄。
  - `route_stats`：動態計算之 7 日、30 日、90 日均價與歷史最低價。
  - `deals`：偵測符合高評分之神價事件與推薦理由。
  - `search_tasks`：具備優先級與 Tier 1~4 的智慧排程巡邏佇列。
