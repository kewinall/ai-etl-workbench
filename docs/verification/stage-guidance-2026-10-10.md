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

## 里程碑 3：結果、歷史與接續入口

- 專案歷史 Task 以權威狀態顯示接續分類，開啟精確 Run／階段；等待時才每 5 秒唯讀輪詢。
- 舊版節點、Log、SQL、Hop XML／下載集中收合，時間軸依查看 Run 讀取。既有下載入口保留。
- 標準答案不再獨立切換 Run；歷史版與過期狀態停用編輯，下載及讀取仍可用。
- 來源欄位按來源分組，轉換選單呈現來源名稱／左右表；不可變識別與轉換契約仍在進階詳情。
- 規格語意退回與 QA 證據問題導向各自階段；執行結案後依後端資格提供修正版，QA 修正仍要求新目標及重新核准。
- 離線立即停用操作，恢復連線只讀回核；未派發任何模型或 ETL。
- 最終隔離 PostgreSQL 全回歸：2017 passed、139 skipped、1 warning，45.47 秒。跳過範圍同里程碑 1；不是 Native 全鏈證據。
- 瀏覽器階段回歸與舊產物下載：15 passed，25.2 秒。真實隔離 API 只驗證新 Task／Run／輸入核准；其他分支使用 browser-only 合成資料，不冒充已持久化模型或 Hop 結果。
- 390／768／1440px 均無頁面水平溢出，七階段鍵盤與版本重載／返回 PASS；390px 畫面已人工檢視。
- 最終瀏覽器回歸找到並修正兩個問題：唯讀版本載入不應觸發寫入離開保護；QA 修正版定位需等待表單及狀態更新完成才聚焦。
- 既有 5183 Release 唯讀回歸：TASK-20260917-0007／Run d8abcc97-e5d7-4f83-9d47-b244e03730e7，Release a76bae7f-3b13-4dda-ac3f-68f8b41081de；ZIP 10452 bytes，下載 SHA-256 與伺服器一致：f32b964c8071d37dd854f653320eb4ce41041ae01e92220a026aa27d9bb8da2d。未重跑、改寫或重新核准該 ETL。

## 使用、範圍與接續

預覽：http://127.0.0.1:5197。只使用獨立合成 Task；此環境沒有模型／ETL Worker，模型、Developer、QA 及 ETL 派發均關閉。既有 5183 部署保持原 image。

```powershell
wsl -d RockyLinux9 -u root -- docker compose -f /mnt/d/ChatGPT/ai_agents_v2/deploy/compose.stage-guidance.yml up --build -d
# 停止獨立預覽，保留資料與產物，不影響既有 Pilot
wsl -d RockyLinux9 -u root -- docker compose -f /mnt/d/ChatGPT/ai_agents_v2/deploy/compose.stage-guidance.yml stop
```

本次三個 UI 工程里程碑已實作並分段驗證；整體 WS-0007 保持 active。尚未更新既有部署，也尚未推送本次專案 commits。原有未提交 test_join_replay_worker.py 保留，不納入本次提交。

下一步：先審閱獨立預覽與本機提交；具備原有模型／寫入／QA／交付核准後，在新的合成案例完成真實模型→Hop→Vertica→QA→ZIP 的每個階段與退回分支，再評估套用既有部署。JSON／資料表來源完整執行仍未驗收。草稿僅暫存目前頁面，重載前需保存新版或另行保留內容。

## 本輪缺口修正（仍為部分完成）

- 控制服務缺席時顯示執行服務未就緒與管理者處理方式；下一步卡片明示前往階段，不冒充派發。
- Join 補正使用既有契約、差異預覽、新版；草稿包含 Join。執行產物及標準答案訂閱共用唯讀更新；設計頁移除重複 SDM，舊版入口依真正歷史產物存在判定。
- 5197 隔離後端回歸：2018 passed/139 skipped/1 warning，45.30s。瀏覽器 16 passed，26.1s（新增 Join 修訂預覽；不代表 Native 全鏈）。
- 真實本機 copilot/gpt-5.4 連線檢查 CONNECTED，完整 trace：ui-accept-model-connection-2026-10-10.json；無工具、無自動重試。前次檢查輸入缺追蹤欄位，未計入通過證據。
- Worker 新增 WORKBENCH_LOCAL_API_CONTAINER/WORKBENCH_LOCAL_WSL_DISTRO，預設維持原容器；控制 Worker 可限 --project-id。服務接通及三案例正式交付尚未完成。
