# WS-0007 v2 階段導引調整

日期：2026-10-10（Asia/Taipei）。此次七個 UI 階段與既有專案 Stage 1–7 驗收分開記錄。

## 基線

- 本機與遠端 HEAD：354418bea291f4370ef7e66e0774f601e26bc0b4。
- 既有未提交修改：backend/tests/test_join_replay_worker.py；保留、不納入本次提交。
- 既有部署：ai-etl-workbench，API image e27398d0d217、Web image 0b7511b392bd，5183。未重啟或改寫既有 Task／Release。
- WS-0007 遠端紀錄仍停留在較早的失敗修正版接續；本次以前端規劃與實際來源為準。

## 里程碑 1：統一版本與狀態

- 新增唯讀 workflow-status，彙整既有 SA／Developer／規格／Hop／QA／Release 讀取與資格，不建立新工作流狀態表。
- 共用 Run 與網址版本；查不到指定版本直接顯示錯誤。舊網址有相容導向。
- 七階段、已完成摘要、責任角色與下一步；歷史、失效與未達前置條件禁止寫入。
- TypeScript／Vite build PASS（現有 bundle 大小提示）。
- 獨立 ai-etl-stage-guide-tests Compose／PostgreSQL／volume 回歸：2013 passed、139 skipped、1 warning，45.72 秒。跳過包括 Native Hop、既有真實執行、Git／PowerShell 與另行部署測試；不等於全鏈驗收。
- 新 API 真實資料庫與瀏覽器驗證仍在進行；未宣稱全鏈通過。

## 下一步

完成唯讀 API 整合測試，再驗證問題定位、差異預覽、修正版建立、斷線與重送保護；最後整理交付、專案接續與窄版／鍵盤。真實模型、Hop、Vertica、QA 與 ZIP 完整執行仍須原有核准與獨立合成案例。
