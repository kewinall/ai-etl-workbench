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

## 里程碑 2：接通操作與退回

- SA、命名、Developer、規格、標準答案、Hop、QA 及交付操作分別接入對應階段；沿用既有 API，不呼叫模型驗收。
- 問題導向需求欄位、修正輸入保留、差異預覽與勾選確認後建立子版。草稿只暫存本頁，重載會清除，文案明示。
- 修訂結果不明須先讀取子版；保留 request key，不自動重送。成功導向須在忙碌保護解除後進行；此問題由瀏覽器測試找出並修正。
- 歷史命名讀取規格保存當時的 contract_id；沒有綁定時不混入目前 Task 契約。
- 操作結果或等待狀態只讀更新相關元件，開啟編輯時不重置草稿；隱藏頁面暫停輪詢。
- 真實隔離 API／瀏覽器版本建立與輸入確認 + 合成歷史、缺失版本、舊 URL、修訂差異、雙擊、回應遺失、狀態過期、輪詢、390／768／1440px 鍵盤：9 tests PASS，19.3 秒。
- 隔離 PostgreSQL workflow／規格／命名回歸：21 passed，1 warning，7.40 秒。
- 隔離 UI：compose.stage-guidance.yml，5197；模型、Developer、QA、ETL 派發均關閉，無執行 Worker。初次缺 migration 導致 readiness 503，已補上有序 migration 後通過。
- 規格退回、QA 補證與真實完整執行的新增 UI 情境仍需擴充，不能用上述合成畫面取代 Native 全鏈。

## 下一步

完成第三里程碑的專案接續入口、舊版下載與結果／歷史整理，擴充規格退回、QA 補證、執行異常 UI 回歸。真實模型、Hop、Vertica、QA 與 ZIP 完整執行仍須原有核准與獨立合成案例。
