# 規格保存／核准接入協作時間線

2026-09-13 已部署 migration 029，於既有 task_run_event 新增 event_context，舊事件預設為空物件。規格保存與人工核准分別記錄 SPECIFICATION_SAVED／SPECIFICATION_APPROVED，包含規格 ID、版本與 checksum；核准事件另包含 approval_id／operator_id。事件與對應資料操作在同一 transaction 中寫入，不另建事件系統。

Run detail API 回傳 event_context，Task 協作紀錄显示可讀取名稱與規格參照。歷史核准事件明示不代表目前仍有效，也不是 Hop／Release 授權；目前有效性須至需求與規格重新檢查。

## 驗證

- 26 項隔離 PostgreSQL 規格／Run／migration 測試通過。
- 規格保存、重複保存、核准、重複核准、保存新版後，只有三筆規格事件，順序為保存 v1、核准 v1、保存 v2；checksum／approval_id 一致。除事件新增外 Run 內容未變動，無 Hop artifact。
- 部署後全站瀏覽器 9 passed（19.9 秒）、2 opt-in skipped。新時間線顯示／390px 寬度測試使用合成 API 回應；不可將其當成真實 UI 核准 DB E2E。
- API ready，execution_enabled=false，CONTROL Worker 已恢復；未追加模型用量，未觸及 Windows DB 或業務表。

## 尚未完成

規格建立／編輯表單、真實 UI→核准→DB→時間線的連續驗收、Worker 下游核准查核、不可變來源、Vertica QA／SDM／Release 仍待完成。此次事件記錄不能替代 P1 E2E 或 P2／P3 驗收。
