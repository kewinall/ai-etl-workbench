# Task／Run HPL 編譯預覽 API

已新增並部署：`POST /api/tasks/{task_id}/runs/{run_id}/specification/compile-preview`。

請求沿用 EtlSpecificationV1；以 Task lock、Run／最新 NamingContract share lock 讀取平台保存內容，與既有 validate 入口共用驗證與錯誤遮罩。有效請求回傳 plan、HPL、checksum、required_checks；明示 `HPL_CANDIDATE_NOT_EXECUTABLE`、`execution_authorized=false`。

不保存 specification／artifact，不派發模型或 Hop，不給予 release／下載核准；不接受外部 XML。新版命名 draft 存在時不能回退使用舊 confirmed 版本。

## 2026-09-13 驗證

- 62 項本機規格、CSV、編譯及 API 錯誤回歸通過。
- 4 項隔離 PostgreSQL + TestClient 整合通過：validate／compile-preview 各驗證重複請求確定性、Run 未改動、specification／hop_artifact／agent_invocation 無新增、任意 SQL 422、Run ID 不一致 409、跨 Task 404、新版 draft 阻擋且不回傳 HPL。
- 建置及部署 API image 完成，CONTROL Worker 測試前正常停止、測試後恢復。沒有修改 Windows DB、歷史任務或部署模型憑證。
- 網站反向代理對新 route 的空請求回傳 422（路由可達及 schema 驗證，不代表完整有效請求驗證）；有效請求的證據為上述真實 PostgreSQL API 整合測試。
- `/api/ready`：ready、execution_enabled=false。
- 部署後網站回歸 8 passed（23.4 秒），真實 Copilot 與 native Worker lifecycle 兩項 opt-in 測試 skipped。未追加模型用量。

## 剩餘範圍

尚未有使用者操作的規格編輯／編譯預覽頁面；尚未保存及核准規格版本，也未接 Worker、不可變來源 bytes、實際 Vertica／HWF／DDL／QA／SDM／Release。預覽 API 不能被當成 P1 成功或 P0–P3 完整驗收。
