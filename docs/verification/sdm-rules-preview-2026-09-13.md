# SDM 轉換規則預覽驗收

## 修正範圍

原 SDM 預覽僅顯示輸出欄位與 lineage，後端文件已有的來源、目標、寫入、篩選與聚合規則未呈現。現在同一個預覽加入這些資訊，不改動規格、不追加核准，也不開放 Release。

- 來源識別、目標 schema/table、APPEND 中文說明。
- 篩選欄位、比較方式、原始比較值與型別，ALL 與 EXCLUDE_UNKNOWN 說明。
- 無篩選、無聚合及整體聚合的明確文案。
- 分組欄位與 SQL_NULLS 政策；既有輸出順序、lineage 及指紋保留。
- 保留「尚未產生 Excel」與非 QA／Release 通過提示。

## 本次證據

- `npm run build` 通過，已重建並部署隔離 Pilot 的 web 容器。
- `specification-live.spec.ts`、`task-workspace.spec.ts`：2 passed，9.5 秒。
- 規格案例由網站建立、保存、核准並從 PostgreSQL API 回讀，再檢查 SDM 的 `ai_sample.spec_ui_only`、APPEND、`amount > 100.00`、DECIMAL、category 分組與 EXCLUDE_UNKNOWN。
- 390px 寬度檢查無整頁水平溢出；另一案例驗證六頁籤、合成歷史產物下載契約、鍵盤與深連結。
- Task：TASK-20260913-0210；Run：eaf18120-b4ae-4b36-93e9-836777dd24d8；Specification：8eb86b64-ae89-4fb3-9273-e2a030e86938。

## 未完成與限制

這是 SDM 網站語意呈現驗收，不是 Excel、Hop 或 Vertica E2E。本輪沒有新增模型呼叫或 Vertica 寫入；Excel 產生器、正式 QA 與 Release 文件仍須後續實作及驗收。完整 P0–P3 目標未達成。

## 後續分支與政策檢查

同日後續部署加入 SDM 文件版本、候選狀態旗標、ALL／EXCLUDE_UNKNOWN、APPEND 與 SQL_NULLS 檢查。不接受與畫面說明不同的政策，避免將不支援的回傳結果顯示成有效規格。

- 建置通過；部署後兩項瀏覽器回歸 2 passed（10.5 秒）。
- 新真實規格控制流程：Task TASK-20260913-0212、Run 521226b5-c7a3-4e89-a796-da5c4a276b60、Specification 80012005-e143-4dd6-8b28-a0de26463c15。
- 在此真實流程中另攔截 SDM 回應，驗證無篩選、直接對應、IS_NULL／IS_NOT_NULL、空字串、false、0 與整體聚合的呈現。
- 合成錯誤回應涵蓋規格指紋不符、ANY、INCLUDE_UNKNOWN、不同聚合 NULL 政策、TRUNCATE、冒稱 QA／Release 通過；各情境均顯示錯誤並清除表格與規則。
- HTTP 503 後可重新讀取並恢復有效預覽，舊錯誤消失。

上述分支使用瀏覽器回應攔截，沒有保存虛假規格或 QA 證據，也不代表後端接受這些規則。正式模型與 Vertica 驗收限制不變。
