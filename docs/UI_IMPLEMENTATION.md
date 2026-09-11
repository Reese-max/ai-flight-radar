# Figma UI 2.0 實作與交付

設計來源：[Figma 桌面首頁 6:2](https://www.figma.com/design/JPE9g17smfFB6R7eKxjRDr?node-id=6-2)。保留既有 Python/FastAPI 架構，使用 HTML、CSS tokens 與原生 JavaScript，不新增 React 或建置期 Tailwind。桌面側欄、三／二／單欄票價卡、手機底部導覽、篩選抽屜與詳情操作列皆實作。

## 已接通

探索、篩選、分頁、目前載入範圍排序、日期比較、票價詳情、規則式自然語言解析後人工核對、手動查價、API Key 驗證／清除、實際程序心跳、瀏覽器本機追蹤 CRUD。伺服器資料文字使用 DOM `textContent`，來源連結只接受明確 Google Flights URL；未提供資料不填假值。

`GET /api/ui/quotes` 先取每組查詢的最新快照，再套預算與六小時有效期，避免把舊低價錯當現在售價。行李與最終含費總價未知。`GET /api/ui/dates/{origin}/{destination}` 每一列為出發／回程日期組合，而非觀測時間走勢。快照的折扣只比較其之前的同查詢歷史，至少五個先前觀測日。

API 保留舊端點，相容原有 CLI；`python main.py server` 改用 `api.site:app` 以載入新版資產。雲端使用 `deploy/start.py`。

## 功能界線

「追蹤清單」只保存在目前瀏覽器，沒有新增伺服器個人追蹤服務；頁面、對話框與儲存成功提示均明示不會啟動通知。自然語言仍為既有規則解析，不改稱完整 AI 自主搜尋。搜尋、切換頁面及重新整理不會觸發外部查價。

Figma 的金額未複製進 production 資料。只有 `tests/browser_smoke.py` 存在刻意標識的合成 API fixture。新安裝以真實空白／累積中狀態呈現。

## 資產與可及性

CSS 色彩與字體依 Figma tokens。`web/assets/icons/` 為 Figma 原節點匯出的 SVG：radar 6:5、calendar 6:22、bookmark 6:27、settings 6:31、search 6:73、check 6:197。字體以 Google Fonts CSS 引用及系統 fallback 使用，不提交字體檔。

主要操作最小 44 px、HTML 原生 dialog 的焦點管理與 Escape、表單標籤、aria-live 狀態訊息、跳到主要內容及減少動態偏好。API CSP 限制 script 為 self，CSS/字體僅允許使用中的 Google Fonts 網域。無第三方 JavaScript CDN。

瀏覽器驗收包含 1440 px 桌面、390/360 px 手機、無水平溢出、篩選驗證、詳情跳轉、文字注入防護、本機追蹤、金鑰不永久儲存及來源失敗。完整無障礙標準符合性及真實 iOS VoiceOver 仍需獨立檢測。
