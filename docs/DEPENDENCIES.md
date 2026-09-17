# 依賴鎖定與可重建安裝

本儲存庫的 CI、部署與 Docker 建置一律從**已提交的解析結果**安裝，不在安裝時才解析版本範圍。人工編輯的清單保留彈性範圍，實際安裝圖由鎖檔固定。

## 檔案角色

| 檔案 | 角色 |
| --- | --- |
| `requirements.txt` | 人工編輯的應用程式依賴清單（允許範圍） |
| `requirements-dev.txt` | 人工編輯的測試依賴清單，以 `-r requirements.txt` 涵蓋應用程式 |
| `requirements-lock.txt` | 由 `requirements.txt` 產生：全版本鎖定 + sha256 雜湊 |
| `requirements-dev-lock.txt` | 由 `requirements-dev.txt` 產生：含 pytest、playwright 等測試鏈 |
| `cloudflare/package.json` | 人工編輯的 Worker 依賴清單 |
| `cloudflare/package-lock.json` | npm lockfileVersion 3 解析結果 |

## 安裝

```bash
python -m pip install -r requirements-lock.txt        # 應用程式
python -m pip install -r requirements-dev-lock.txt    # 測試（含應用程式）
cd cloudflare && npm ci                               # Worker / Wrangler
```

`pip` 見到 `--hash=sha256:` 會自動驗證每個發行檔案的完整性；`npm ci` 會在 `package.json` 與 lock 不一致時直接失敗，且永遠寫入 `node_modules` 全新安裝。

## 更新依賴（reviewable update）

1. 編輯人工清單：`requirements.txt`、`requirements-dev.txt` 或 `cloudflare/package.json`。
2. 執行 `bash scripts/refresh-locks.sh`，重新產生三份鎖檔（uv `pip compile --generate-hashes --universal --python-version 3.12`，npm `--package-lock-only`；解析器版本固定於腳本內）。
3. 在 PR diff 中審核**依賴圖變更**：鎖檔裡的 `name==version` 行、雜湊變更、`resolved` URL。這是本次變更真正的供應鏈差異。
4. CI 的 `dependency-gate` job 會從兩份鎖檔全新安裝，再重跑 refresh 腳本；若有任何已追蹤檔案被改動（清單改了但鎖檔未重產生、或解析器輸出漂移），即失敗。

## 回滾（rollback）

依賴圖由 git 鎖定，回滾即還原清單與鎖檔：

```bash
git revert <更新依賴的 commit>   # 或 git checkout <舊 commit> -- requirements*.txt cloudflare/package*.json
```

還原後的 lock 與當時 CI 通過的圖完全相同，不需重新解析。若只要退回單一套件：把清單中該套件改回舊範圍、跑 `refresh-locks.sh`、確認 diff 只含該套件及其相依變動。

## 第三方 GitHub Actions

`.github/workflows/` 與 `cloudflare/templates/` 內所有 `uses:` 固定到已審核的完整 commit SHA，並以 `# vX.Y.Z` 註解標示可讀版本。升級 action 時：查閱該版本的 release notes，把新 tag 的 commit SHA 填入 `uses:`，更新註解，於同一 PR 說明理由。
