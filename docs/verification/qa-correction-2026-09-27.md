# QA 未通過後的受控補正（2026-09-27）

## 原因與範圍

第 19 個正式案例的修正版 Hop 結果為 6/6 EXACT_MULTISET MATCH，但 QA 指出文字「依序」可能要求來源列序；凍結標準答案不驗證列序。因此維持 NEEDS_REVIEW，未核准 QA 或 Release，未修改凍結標準答案，也不將多重集合相同宣稱為順序相同。正式交付仍為 18/20。

原有修訂入口只支援未寫入的需求補正，以及已核對結案的 Hop 失敗；不支援成功執行後的 QA 補正。本次新增同一 revisions API 的受控分支，不建立第二套 Task。

## 保護條件

- 僅 Hop 已明確完成、無 lease、無待處理 Hop dispatch 的版本。
- 最新 QA 必須為經驗證的 FAIL 或 NEEDS_REVIEW；PASS、未知、待回應、過期、損毀紀錄均不符合。
- 重建當前證據 context 並比對 checksum；不得已有 QA 核准或子版本。
- 請求須攜帶畫面提供的 QA revision checksum，綁定原輸入、模型審查及 context。
- 新目標必須是 ai_sample 中不同且尚未登錄的表；實體表不存在仍由後續建立目標的既有 gate 檢查。
- 原版只結束待審流程（CANCELLED），保留 HOP_EXECUTED_QA_REQUIRED outcome、原輸入、QA 與所有執行證據。新增 QA_REVISION_LINKED 事件說明原因。
- 新版未核准、未寫入，重新走 Requirement Gate；不重用下游核准，不自動重跑原 Hop。

## 本次驗證

- 隔離 PostgreSQL 全套回歸：1268 passed、46 skipped、1 warning，27.19 秒，exit 0。略過的原生整合項目不計為通過。
- 新增 18 項 QA revision 權限單元案例及 1 項隔離 PostgreSQL 修訂交易案例。交易測試使用合成 QA offer，不冒充真實模型驗收。
- 前端 TypeScript/Vite build 成功。
- 部署前確認 0 個 QUEUED/RUNNING Run、0 個 RESERVED 模型呼叫，再更新 API/control-worker/web。
- 真實第 19 案唯讀瀏覽器測試：1 passed（4.1 秒）；表單可開啟，390/768/1440 寬度無水平溢出，無頁面錯誤、無寫入請求，前後事件與 QA binding 相同。

## 尚未完成

真實提交補正與新一輪模型／Hop／QA／Release 尚未執行。需先確認「依序」的業務意義；不得因修訂入口可用就宣稱第 19 案已通過。第 20 案、量測報告／人工基準、維運與還原驗收亦未完成。

knowledge-workspace 尚未同步；目前環境沒有本機 checkout，先前同步受權限限制。此文件是專案內去識別化的接續證據，不包含私有 Task/Run ID、連線、原始 log 或憑證。
