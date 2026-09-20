# 規格保存、歷史與人工核准 API

2026-09-13 已在隔離 Pilot 套用 migration 028 並部署 API。沿用 `platform.specification`，新增 nullable Run／NamingContract／checksum 綁定，舊規格不回填或覆寫。新增 `specification_approval` 保存單一 Operator 核准；不建立第二套 Task。

API（前綴 `/api/tasks/{task_id}/runs/{run_id}`）：

- `POST /specifications`：接收 EtlSpecificationV1，重新驗證當前 Run、輸入核准、命名及設定後保存；同一最新內容重複送出回傳同版本。
- `GET /specifications`：回讀此 Run 的規格及核准歷史，計算目前的 `approval_effective`。
- `POST /specifications/{specification_id}/approve`：接收 `{"content_checksum":"<64 hex>"}`，只接受最新有效版本，舊版本／checksum／上游不符回傳 409。

所有入口均不派發模型／Hop，不宣告執行或 release 權限。保存回傳 `SAVED_NOT_EXECUTABLE`，核准回傳 `SPEC_APPROVED_NOT_EXECUTABLE`。核准歷史不刪除；新規格或上游變更後 `approval_effective=false`。

資料庫 trigger 拒絕改寫已綁 Run 的規格內容（僅 is_current 可更新）及核准紀錄。舊規格仍可依既有功能讀取。規格版本的 Task 鎖與既有 Run 控制共用。

## 驗證

- 62 項本機規格／編譯／CSV／預覽 API 回歸通過。
- 26 項隔離 PostgreSQL 整合測試通過，涵蓋 6 項規格 API、既有 Run 佇列與 migration 回歸。
- 新保存／核准案例證明：重複保存不新增版本；核准 checksum 不符 409；重複核准同筆；新版本停用舊有效核准但歷史可查；修改上游需求後歷史核准仍在但無效；DB 拒絕修改規格與核准內容；無 Hop artifact 新增，Run 未被派發或改為成功。
- migration 028 在隔離 PostgreSQL 實際套用一次；部署時重跑無重複套用。
- 部署後網站 8 passed（20.2 秒），真實 Copilot／native lifecycle 兩項 opt-in skipped。`/api/ready` 為 ready／execution_enabled=false；新歷史 route 對不存在 Task 回傳 404。
- CONTROL Worker 已恢復，不開啟模型派發、不新增模型用量、不修改原 Windows DB。

## 尚未完成

規格編輯／保存／核准尚未接到使用者網站，尚無 UI 點選核准驗收。規格操作也尚未彙入 Task 協作時間線。下游執行必須再次查核有效核准，不能只看歷史 approval_id；Worker 接線尚未完成，因此本批沒有解除 execution gate。

來源 bytes 不可變綁定、HWF／DDL、Vertica 真實寫入與 QA、SDM／Release、P2 四情境及 P3 成效報告仍待完成。P0–P3 尚未達標。
