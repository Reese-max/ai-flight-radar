# Cloudflare 準備版本

這個目錄是**可套用到原專案的新增模組**，不是已部署服務。
基準：`Reese-max/ai-flight-radar`，`0798ce99c0abc46e630a31d2cb6fa6025027860f`。

採 Workers Static Assets + JavaScript Worker API + D1；原 Python 查價器留在限量批次。
不修改 `web/`、原 FastAPI、原 SQLite、原 Docker 或既有 GitHub 排程。
不加入假票價、預設金鑰、帳號 ID 或已存在的 D1 ID。

## 不需網路的測試

需 Node.js 22.13 以上（含 `node:sqlite`）及 Python 3.12 以上。
在儲存庫根目錄：

```bash
node --test cloudflare/tests/*.test.mjs
python -m unittest discover -s cloudflare/tests -p 'test_*.py' -v
python cloudflare/scripts/collector.py
```

最後一行只顯示 dry-run，不連 Cloudflare 或 Google Flights。
測試使用 SQLite 實作的 D1 介面替身，不代表 Cloudflare runtime 已驗收。

## 接回原網頁

將本修改包套用到原 repo 後：

```bash
cd cloudflare
node build.mjs
node scripts/local-server.mjs
```

本機預覽位址是 `http://127.0.0.1:8788`；只綁定 loopback，不是公開網址。
建置程式沿用原圖示、CSS 與 JavaScript，只在生成副本中調整批次狀態文字。
若原 UI 的必要標記改變，會停止建置要求檢查，而不是默默修改錯誤位置。
獨立解壓修改包沒有原 `web/`，直接建置會缺檔；必須先套用到原儲存庫。

本機 runner 預設沒有管理或 collector 金鑰，寫入會被拒絕；不自動產生或展示秘密。
本機測試資料位於 `cloudflare/.local/`，請勿提交。

## 雲端工具

`package.json` 的 Wrangler 固定為官方已發布的 `4.131.0`。
目前環境無法下載套件，因此沒有假造 `package-lock.json`，也沒有執行 Wrangler。
網路可用時先執行 `npm install`、審閱鎖檔、執行 `npm run build` 及 `npm run wrangler-check`。
`wrangler-check` 僅 dry-run；不是部署。

完整設定、可用範圍、免費層限制、金鑰與驗收見 `../docs/CLOUDFLARE.md`。
