# 專案最新 Run 摘要

新增 GET /api/projects/{project_id}/summary，以及專案工作區的「專案進度」區塊。保留設定／歷史 Task 頁籤順序及新增／編輯流程。

摘要以每個 Task 最新 created_at/run_id 的 Run 分組，每個 Task 只計一次。無 Run 顯示「尚未建立準備版本」；QUEUED、NEEDS_REVIEW 等分開顯示。舊 Task SUCCEEDED 不計為 Run 成功，Run SUCCEEDED 也不代表 QA／Release 核准。

API 不回傳來源設定、連線或機密；失敗回傳通用 503。網站更新時清除舊內容，讀取錯誤不顯示零筆；可重試，並提供歷史 Task 的操作指引。摘要不計算核准有效性或 QA，明確回傳 qa_evaluated=false／release_evaluated=false。

## 驗收

- PostgreSQL 測試初次因 fixture 錯誤預期初始 NEEDS_REVIEW 失敗；依實際 enqueue 契約 QUEUED 修正測試及 cancel_unstarted 入口，未修改產品狀態流程。
- PostgreSQL 重跑 1 passed（0.39 秒）：舊成功 Task 無 Run、首次排隊、取消、新 Run 取代旧 Run 的計數驗證。
- 前端建置成功。API/web/CONTROL Worker 已部署並啟動。
- 瀏覽器 3 passed（11.3 秒）：真實空專案→新增 Task→API/畫面更新、合成 503 不冒充零筆、恢復讀取、390px，以及既有專案新增／編輯／取消／重載與歷史 Task／節點／Job 導覽。

本次無模型、Hop 或 Vertica 呼叫。最新 backend image 也含前幾輪 SDM 檢查模組，但正式 SDM 產生及封裝下載入口仍未開放。openpyxl 正式 renderer 的選擇仍待確認，並未將自動 goal continuation 視為使用者同意。完整 P0–P3 目標未達成。
