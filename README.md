# AI ETL Workbench

> 此 repository 收錄本機 v2 的測試專案基準（原名 FlowForge AI），不是已完成驗收的正式版本。現有操作文件包含歷史設計，請同時閱讀 [目前限制](docs/known-limitations.md)。
>
> 不包含本機 `.env`、SSH 金鑰、資料庫、Hop 安裝包、來源掃描資料與執行產物。複製 repository 不會取得既有專案／Task 歷史；它們仍保存在原本的平台資料庫。請自行安裝 Hop、Java 與必要驅動，並依實際目錄調整 `.env.example` 中的路徑。部分 scripts 尚依賴原開發機的工具路徑，不保證乾淨機器一鍵啟動。

## 歷史操作文件

Windows 11 原生 POC：React + Vite、FastAPI、獨立 Python Worker、PostgreSQL-first repository 與 Apache Hop `hop-run.bat` 執行邊界。未提供 PostgreSQL 連線前，預設以 mock fixture 啟動完整 UI。

## ETL Analyzer（ETL 結構與邏輯分析）

網站目前專注於產生與驗證 Apache Hop Job。既有轉換案例的元件統計、常見模式與生成規則整理於 [`docs/hop-generation-reference.md`](docs/hop-generation-reference.md)，供後續擴充生成器時使用。

Parser 會建立統一的 Canonical ETL Model，呈現節點、流程連線、來源／目標、Filter、Join、Lookup、Aggregation、SQL、Parameter、Variable 與子流程相依性。上傳內容僅存於 `runtime-temp`，分析結束後自動清除；遮蔽後的內容、結果、紀錄與模型用量寫入 PostgreSQL。

XML 結構解析不依賴 AI；AI 僅用於商業邏輯摘要與複雜元件 Review。預設掃描目錄為 `D:\ChatGPT\ai_agents_v2\scan`，可用 `.env` 的 `ANALYZER_SCAN_ROOT` 調整。來源檔只讀取、不複製；密碼、Token、Secret 會遮蔽後才將 XML 與分析結果存入 PostgreSQL。相關資料表與 Task 欄位由 `010` 至 `013` migration 建立。

## 快速開始

```powershell
cd D:\ChatGPT\ai_agents_v2
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

- 網站：`http://127.0.0.1:5173`
- API 文件：`http://127.0.0.1:8765/docs`（避開本機既有的 8000 服務）
- 停止及清除暫存：`.\scripts\stop.ps1`
- 測試與前端建置：`.\scripts\test.ps1`
- 建立展示 Task：`.\scripts\demo.ps1`

## PostgreSQL 待填設定

複製 `.env.example` 產生的 `.env`，將 `DATABASE_URL` 的 `TODO_*` 全部替換，再將 `APP_MODE=postgres`。執行 migration：

```powershell
$env:DATABASE_URL='postgresql://user:password@host:5432/ai_agents'
.\scripts\migrate.ps1
```

Migration 包含 Task、Source Profile、規格版本、Agent Run/Handoff、HPL/HWF metadata、Static/Semantic/Execution 驗證、Hop log chunk、用量與 Provider 健康檢查。驗證策略固定 `FIRST_10_VALID_ROWS`、最多寫入 10 筆並做 post-write count。

## 儲存政策

永久檔案只允許 `hop-project` 內的 `.hpl`/`.hwf`。需求、Markdown、JSON、Prompt、Agent I/O、Handoff、Validation、Troubleshooting、Hop/run log、stdout/stderr、usage、錯誤與版本資訊均存 PostgreSQL。`runtime-temp` 只供短期執行使用，由 stop/worker 清除。CSV 只記錄使用者指定的來源路徑，不複製到平台。

## 模型與帳號

網站不保存 Codex 或 GitHub 帳密。`CodexCliAdapter` 與 `CopilotAdapter` 共用介面；健康檢查只探測 Windows CLI 的安裝與登入能力。Copilot 公司帳號是否可用仍取決於 `gh`、Copilot extension 與組織政策。CLI 無法提供精確 token 時，資料庫明確記為 `UNAVAILABLE`。

## 目錄

- `frontend/`：所有已確認頁面與響應式 UI
- `backend/app/main.py`：API 與 mock fixtures
- `backend/app/worker.py`：獨立 Worker 入口
- `backend/app/adapters.py`：統一模型 Adapter
- `database/migrations/`：PostgreSQL schema
- `hop-project/`：唯一永久產物 HPL/HWF
- `scripts/`：setup/start/stop/test/demo/model/Hop 檢查

## POC 限制

PostgreSQL 連線未提供前，網站以 mock 展示；正式 queue claim、真實 Source Profiling、Agent CLI 生成與 Hop 寫入只在連線與本機帳號驗證完成後啟用。這些入口與資料模型已保留，但不會偽裝成已成功連線。
# PostgreSQL / Vertica 目標資料庫

新建或編輯 Task 時，可選擇 `POSTGRESQL` 或 `VERTICA` 作為寫入目標。平台系統資料仍一律保存在 PostgreSQL；只有 POC 資料寫入目標依 Task 設定切換。

Vertica 後端設定放在 `.env`，網站不保存或顯示密碼：

```env
VERTICA_HOST=127.0.0.1
VERTICA_PORT=5433
VERTICA_DATABASE=VMart
VERTICA_USER=dbadmin
VERTICA_PASSWORD=TODO_VERTICA_PASSWORD
VERTICA_TLSMODE=disable
```

Apache Hop 需要 Vertica JDBC 驅動。`scripts/setup.ps1` 會將官方驅動安裝至 Hop JDBC 與 Generic database plugin 目錄。Task 完成後，平台會直接連到所選目標資料庫執行 post-write count。
