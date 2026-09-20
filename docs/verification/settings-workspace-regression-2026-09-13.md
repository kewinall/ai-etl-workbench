# 設定與專案工作區合併回歸

## 本輪結果

後續合併重跑：20 passed、2 skipped，46.0 秒。包含新增的設定讀取恢復、工具路徑不完整回讀、歷史狀態篩選、專案儲存鎖定及 Release HTTP 阻擋。兩個跳過項目仍是真實 Copilot 與原生 Worker lifecycle。

此次之前的一輪為 19 passed、1 failed、2 skipped：換檔測試按保存後立即 GET，未等待修訂 POST 提交，讀到上一版。修正為等待指定父 Run 的 revisions 回覆 201，再獨立 GET 核對新 ID、parent_run_id、來源 checksum 與舊版保留；沒有移除父版本斷言或放寬業務結果。另避免從已因 UI reload 失效的瀏覽器 response 讀 body。單項及全套重跑皆通過。

最新實際控制資料：規格 Task TASK-20260913-0171，Run 294b6b98-a595-45f9-96dc-ae6ae11e0a1e，Specification d33cd11e-9da8-4f17-9875-f0d74f3b96ca；上傳 Task TASK-20260913-0173，原 Run b2b43634-f4d3-467b-a393-989904579cd6，換檔 Run efeade23-24b0-4656-a5fa-776eb788418c。原來源仍為 39 bytes、2 records、execution_authorized=false。

同批隔離後端回歸：306 passed、72 skipped，5.06 秒；WORKBENCH_ALLOW_DATABASE_TESTS=0、WORKBENCH_NATIVE_HOP_STAGING_TEST=0，排除會初始化主機 DB 的 test_api.py。此數字不包含真實資料庫、模型或 Hop E2E。服務 ready、execution_enabled=false。

以下保留較早批次結果，勿與上列計數加總：

部署新版 web 後執行 frontend/tests 全套：16 passed、2 skipped，43.9 秒。
兩個跳過項目為真實 Copilot 呼叫與 Windows 原生 Worker lifecycle；本輪未重新消耗模型額度。
服務 /api/ready 回傳 ready、execution_enabled=false。未啟用 Vertica 寫入。

## 證據與涵蓋範圍

| 項目 | 證據類型與結果 |
|---|---|
| 專案新增、編輯、取消、重載、預設繼承、命名字典、建立 Task | 實際 UI／API，含 API 回讀 |
| 專案未儲存離頁、延遲讀取不覆寫選擇 | 瀏覽器互動；延遲讀取測試使用受控回應 |
| AI Profile 儲存重載、取消、不觸發模型 | 實際設定 API；測試後還原原設定 |
| 多 Profile 草稿隔離、延遲儲存鎖定 | 合成 API；不代表模型服務可用 |
| 工具路徑儲存回讀、機密草稿清除、離頁提醒 | 合成 API；沒有保存真實密碼或更換執行路徑 |
| 跨設定分類草稿、失敗後保留輸入、取消分類 | 合成 API；保存驗證策略不得覆寫未保存的連線 Host |
| 驗證策略儲存重載與不可停用政策 | 實際 API；測試後還原原設定 |
| Task 六頁籤、節點、Log、HPL／SQL、下載、深連結、窄版面 | 合成歷史產物的 UI 契約；實際 Task 未被標記成功，不是 Hop E2E |
| 需求版本、規格保存／核准、來源上傳／換檔 | 實際 UI → API → PostgreSQL；來源結構由 CONTROL Worker 驗證，沒有模型與 ETL 執行 |

本次實際控制資料證據：

- 規格 Task：TASK-20260913-0144；Run：4d9fb249-f12a-418a-bc04-2c89291dc7df；Specification：bcef6c0c-4f1c-42c6-a620-c51aa14a389b。
- 上傳 Task：TASK-20260913-0146；原 Run：fd2a43c7-e376-40fe-a6eb-af0637aff05a；換檔 Run：018f39f9-70c2-4ded-bd85-26bd065ccade。
- 原來源 39 bytes、2 records，SHA-256：8f9a819e68e2b4dcd8d098a7d3a838e144a8cc3fb7c70ff2d38965c93868e8c6。狀態 CSV_STRUCTURE_VALIDATED_NOT_EXECUTABLE，execution_authorized=false。

## 本輪修正

- 分組設定只回讀已保存分類；保留其他分類草稿。新增取消單一分類與離頁提醒。
- AI Profile 保存期間鎖定欄位；保存一張卡不覆寫其他卡。
- 工具路徑結果顯示在原分類，保存後回讀；機密仍僅寫入，不回讀。
- 專案草稿已涵蓋頁內切換、全域導覽與取消返回。完整瀏覽器 history stack／forward 拓樸仍未全面驗證。

## 尚未達標

這不是 P0–P3 完整驗收。仍缺真實 Vertica 連線與授權測試範圍、正式 Hop 派發與 QA／SDM／Release、四案例完整證據、20 案例與人工基準。原生 Hop 初始化失敗證據另見 native-worker-failure-2026-09-13.md，本輪沒有重跑該測試。
