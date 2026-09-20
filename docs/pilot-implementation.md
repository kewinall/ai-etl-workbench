# 內部 Pilot 實作紀錄

目前工程與網站整合進度請以 [P0–P3 當前交付狀態](p0-p3-status.md) 為準；以下保留歷次實作與驗收紀錄，不應將歷次測試數累加成整體完成度。

更新：2026-09-13。這是階段性驗證，不表示完整 Pilot 已完成。

## 最新更新：SA 唯讀狀態與結果畫面

- 新增 GET /api/tasks/{task_id}/runs/{run_id}/sa-invocation，驗證 Task/run 範圍；僅回傳狀態、provider/model、checksum、用量摘要、受控錯誤碼與驗證後 review，不回傳原始 prompt/context 或無效模型原文。
- Task 版本內新增「SA 呼叫狀態」與重新載入按鈕。顯示尚未派發、派發意圖已保存、結構驗證通過但未核准、過期結果及結果未明。
- Token 不完整或非 EXACT 時顯示不可用，不當成零；版本不再符合目前設定時加上不可沿用核准提示。SA 建議不等於執行或交付核准。
- 修正證據檢視文案：表示本次檢視不會呼叫模型，而非推斷整個版本从未呼叫模型。
- 讀取介面不觸發任何派發或重送，dispatch_available=false；尚未開放付費模型呼叫入口。

本輪驗收：35 項選定測試通過（20 項 PostgreSQL 整合與 15 項 SA 測試），包括空紀錄、派發中、完成／未知結果讀取及錯誤 run 拒絕。5 項瀏覽器流程通過，包含真實 API 的空狀態與重新載入按鈕；完整模型結果的 UI→模型→DB E2E 尚未驗收。

下一步：非同步 SA Worker 領取與明確的模型費用授權；真實連線、逾時核對與完整 Pilot 驗收仍未完成。

## 前一階段：單次 SA 協調流程串接

- 新增 dispatch_sa：明確授權 → durable reserve → 讀取 Profile／機密 → 再檢查目前版本 → SA Gateway → journal 保存 review 與 trace。沒有授權時不建立派發，也不呼叫模型。
- Gateway 回傳的已知用量與 checksum 隨結果保存；讀取設定、呼叫或保存失敗時保留待核對狀態。若最終資料庫寫入不可用，先前的 DISPATCH_RESERVED 仍阻擋重複派發。
- 同一版本第二次派發會衝突，失敗不自動重送；沒有推進 ETL/Release 狀態。
- 目前是供 Worker 使用的內部單次動作，尚未由排程／API／UI 呼叫。輸入確認不等於模型費用同意；未新增可繞過此限制的前端按鈕。

驗收：容器內 35 項選定測試通過，其中 20 項真實 PostgreSQL 整合與 15 項 SA Gateway/schema 測試。新增成功與 provider 失敗案例使用注入模型回覆，驗證呼叫只有一次、結果用量持久化、原始 provider 錯誤不外洩，以及再次派發被阻擋。既有 5 項瀏覽器流程回歸通過。

邊界：沒有呼叫真實 Bedrock/LiteLLM provider；此次不是模型 E2E。自動 SA Worker 領取、派發授權表單、讀取呼叫結果 UI、當機後逾時核對仍待補齊。下一步先接唯讀狀態／結果與明確授權入口，再做有費用提示的真實連線驗收。

## 前一階段：SA Gateway 與持久化派發基礎

- SA Gateway adapter 接入既有 LiteLLM Gateway，固定 requirement_gate 路由，檢查輸入核准、目前版本、程式 Gate 與模型名稱；輸出再經 SAReviewV1 驗證。prompt/schema/context/output checksum 與已收到的用量整理為 trace。
- Gateway 的暫時性錯誤重試及 JSON 格式補正沿用既有上限；SA contract 不合法即停止，不新增隱藏的 schema 重試。失敗只保留固定錯誤碼、checksum 與已知用量，不回傳無效模型原文。
- migration 025 在既有 agent_invocation 增加 run_id，pilot_sa 對每個 run 建唯一派發索引，不另建第二套 invocation 表。
- SAJournal.reserve 在交易中核對版本與核准，先保存 DISPATCH_RESERVED、完整 context、prompt 與 schema。再次 reserve 一律衝突，不因程式重建連線而重送。
- 結果可保存為 VALIDATED_NOT_APPROVED；上游已變更則 STALE_RESULT_NEEDS_REVIEW。結果未知可保留 OUTCOME_UNKNOWN_NEEDS_REVIEW，不能自動重送；完成狀態不能經 finish 再覆寫。
- 此基礎尚未組成公開派發流程：自動 Worker、UI 派發、逾時偵測、模型憑證讀取、呼叫前最後核對及 Gateway trace/usage 完整寫入 journal 仍待接通。不要直接呼叫 adapter 來繞過持久化派發。

### 驗收

- 126 項後端測試通過（Gateway 以注入模型回覆驗證，未連外）；18 項真實 PostgreSQL 整合通過，含派發防重、不確定結果保留與終態不可重複保存。
- 既有 5 項瀏覽器流程回歸通過；本轮未新增 SA 執行按鈕，不把未串接能力做成可點的空按鈕。
- 沒有發出真實模型請求、沒有 Hop／Vertica 寫入，不能視為 SA 模型 E2E 完成。

下一步：將 durable reserve → 最後設定核對 → Gateway → journal 結果保存串成明確授權的 Worker 動作，再加唯讀狀態與失敗原因 UI，最後才做有費用提示的真實模型驗收。

## 最新更新：SA 證據 context 與輸出驗證基礎

- 新增 GET /api/tasks/{task_id}/runs/{run_id}/sa-context，只讀取指定 Task/run，建立綁定 input/settings checksum 的最小 context，再計算 context checksum。API 不呼叫模型、不保存 AI 結果，也不核准執行。
- 證據包含需求、目標 schema/table、已知需求條件與來源欄位 name/type；不納入連線 metadata、檔案路徑、樣本資料。使用者需求文字本身仍由使用者負責避免貼入機密。
- Context 的 deterministic_gate 是用目前程式規則重新檢查該快照，不是改寫或取代歷史 gate_result；原歷史檢查保留。
- SAReviewV1 輸出 schema 僅允許摘要、問題、證據引用及 NEEDS_INPUT/READY_FOR_REVIEW；拒絕額外 SQL、工具或執行欄位。
- 驗證器拒絕 run/input/context checksum 不一致、未知證據、缺少需求引用、NEEDS_INPUT 沒有問題細節，及模型嘗試將程式 Gate 失敗宣告通過。
- 引用存在僅代表結構與版本可追溯，不證明自然語言摘要真實或規格完整；READY_FOR_REVIEW 不是執行／Release 核准。
- Task 版本內容加入「查看 SA 證據清單」，以可讀欄位顯示，標示模型尚未呼叫；切換版本重新建立檢視狀態。

### 本輪驗收與邊界

- 120 項後端回歸、16 項真實 PostgreSQL 整合、5 項瀏覽器流程通過。SA schema 驗證使用合成輸出測試，不是模型 E2E。
- 瀏覽器使用真實 API 驗證來源證據編號、input checksum、execution_authorized=false、無連線位置，以及切換父版本後不保留新版欄位清單。
- 真實 SA Gateway 呼叫、prompt 版本、模型回覆保存／trace、失敗補正及人工交接尚未接通；本輪沒有產生 AI token 費用或執行 Hop／Vertica。

下一步：將此 contract 接入受控 SA 呼叫與結果保存；明確檢查憑證／路由、保留每次呼叫證據，無有效連線時維持阻擋。

## 前一階段：合成來源欄位補正

- 版本補正新增 source_fields_v1：可新增、移除或修改欄位名稱與基本型別，最多 200 欄；拒絕空清單、空名稱、大小寫不敏感的重複名稱與未支援型別。
- 僅允許單一 has_actual_data=false 的來源；採 metadata 白名單，實體檔案、樣本資料、不明欄位及多來源不開放編輯。未選擇編輯則保留原來源，不讀寫原始檔案或資料庫表。
- 新舊來源欄位參與輸入 checksum、防重比較與原子版本交易；即使只修改來源欄位，也能建立新版並要求重新確認。
- 未修改的欄位描述等允許 metadata 保留；Task 原始私密設定從現有 Task 保留，不從遮罩後的歷史快照回寫。API 僅提供欄位 name/type，不提供原始連線設定。
- Task 畫面可選擇編輯來源欄位、增加或移除欄位、保留原欄位，並在版本摘要查閱欄位清單。

### 本輪驗收

- 111 項後端回歸、16 項真實 PostgreSQL 整合、5 項瀏覽器流程通過。
- PostgreSQL 驗證只有來源欄位改變的新版仍可保存，重送不重複，舊版來源不變，新版未確認前不會被 Worker 領取。
- 瀏覽器驗證新增 created_date DATE、保存重載、API 新版有兩欄而舊版仍一欄，以及重新確認後 Worker 再檢查。
- Worker 日誌：父版 `625746bc-f024-456e-97a7-4d3b5bebbe9d` 為 NEEDS_INPUT；補正新版 `1983c8f7-0314-4040-9d99-5ecfc5729518` 為 CHECKED。測試版本最後取消並保留歷史；沒有外部模型、Hop 或 Vertica 寫入。

邊界：這是合成來源規格編輯，不是實際 CSV/Excel 表頭改寫、自動型別 profiling 或完整 Vertica DDL 型別支援。完整 SA 輸出 schema、證據對照與真實模型串接仍未完成，不能視為完整 Pilot 交付。

下一步：SA 結構化輸出驗證與來源／需求證據關聯；外部模型連線未驗證前仍保持停止，不以 mock 當真實驗收。

## 前一階段：結構化需求條件與確定性缺口檢查

- 新增 RequirementConditionsV1（Pydantic contract），保存於版本快照的 target_config.requirements_v1，隨輸入 checksum 一同鎖定。補正 API 拒絕未定義欄位，不接受模型 SQL 或工具指令。
- 補正表單新增寫入模式 APPEND/REPLACE/UPSERT、資料期間 ALL/RANGE、日期欄位、包含起日、不包含迄日及鍵欄位。初始值未確認，不自動選擇業務條件。
- 新處理版本缺少寫入模式或期間會 NEEDS_INPUT；無效日期、顛倒日期、全部資料與日期篩選衝突、UPSERT 缺鍵或鍵不存在亦暫停。
- 「最近／近期／最新／recent／latest」只是明確列出的文字偵測規則，缺少期間列為 AMBIGUOUS，與全部資料同時出現列為 CONFLICT。這不是自然語言理解，可能需人工改寫；不能宣稱涵蓋全部語意歧義。
- 多來源 Join 結構化規格尚未接通，明確回報 UNSUPPORTED；來源 metadata 不足以辨識日期或鍵欄位也不會猜測。
- REPLACE 僅保存使用者意圖，不授權刪表；所有條件通過仍為 PIPELINE_NOT_READY，不啟動 AI、Hop、Vertica 或 Release。
- 歷史 Gate 結果不回填、不改寫；本輪新執行的 Gate 才採用上述條件。來源結構編輯與完整 SA contract／型別語意驗證仍待完成。

### 本輪驗收

- 101 項後端回歸、15 項真實 PostgreSQL 整合、5 項瀏覽器流程通過。
- 瀏覽器第一次驗收發現選單定位問題，依可存取角色修正測試後全套重跑通過；沒有刪除失敗條件。
- 真實控制 Worker 記錄版本 `3ef96dd3-f29f-497d-a018-170acef80fcf` 為 NEEDS_INPUT，補齊模式與期間並重新確認的新版本 `dcc33eb6-09a8-4e19-b37e-c4cd97e791a8` 為 CHECKED。測試後取消合成版本，保留歷史。
- 瀏覽器本輪驗證 APPEND/ALL 保存與重新確認；日期邊界、相對時間、UPSERT 缺键與未支援 Join 以後端測試驗證，不宣稱真實 ETL 已支援這些操作。

操作：Task 詳情 → 執行準備版本 → 已暫停版本 → 補正需求並建立新版 → 填寫條件 → 保存 → 重新確認 → 重新載入檢查結果。

下一步：來源欄位 metadata 的完整補正、SA 輸出 schema 與證據對照，再進行真實模型連線驗證。完整四案例 Pilot 尚未完成。

## 前一階段：需求補正與重新確認閉環

- 新增 `POST /api/tasks/{task_id}/runs/{run_id}/revisions`，支援需求文字與目標 schema/table 的欄位式補正；不接受任意 source_config 或 SQL。
- migration 024 保存不可修改的 parent_run_id，同一父版本最多一個直接補正子版本；新版仍屬於原 Task/Project，不建立第二套 Task。
- 僅允許初步 Gate 已暫停、尚未寫入且仍與目前設定一致的版本補正。正在執行、已取消、版本過期或沒有變更的請求會拒絕。
- Task 輸入更新、舊版標記被取代、新版快照與事件在同一交易保存。重送相同 request_key 返回同一新版，內容不同則拒絕；原輸入快照、檢查結果與輸入核准保留。
- 新版從 PREFLIGHT 開始，沒有繼承核准；人工再次確認後，由控制 Worker 重新執行初步 Requirement Gate。舊 Task 狀態、既有執行與產物不重設。
- Task 畫面可開啟補正、放棄、保存重載與跳回父版本；舊 requirements/revise 入口對已版本化 Task 回傳 409，避免直接重設舊流程。
- 驗證：88 項後端回歸、15 項真實 PostgreSQL 整合、5 項瀏覽器流程通過。資料庫案例驗證缺需求 → NEEDS_INPUT → 補正 → 新確認 → CHECKED；瀏覽器驗證取消編輯、保存、新舊版查閱及重新確認後 Worker 再檢查。
- Worker 實際記錄父版本 `ff3c5500-c6bf-4fe3-a055-cb1af8b01f5f` 與新版 `074dcfad-4008-4cb7-ae62-282acf1425e2` 的獨立檢查；兩者皆未執行 Hop／Vertica。合成測試版本最終取消，保留歷史。

### 操作方式與邊界

專案 → 歷史 Task → Task 詳情 → 執行準備版本 → 選擇已暫停版本 →「補正需求並建立新版」。修改後保存，核對新版輸入並重新確認，再按「重新載入版本」查看控制檢查結果。

本輪僅完成文字與目標欄位補正。來源欄位結構、日期／Join／寫入模式語意缺口、Naming/Specification 下游核准失效及真實模型／Hop／Vertica E2E 尚未完成。CHECKED 仍暫停在 PIPELINE_NOT_READY，不是 Release。

下一步先補齊結構化需求欄位與 SA contract／缺口對照，再接真實模型驗證；不啟用尚未驗收的 ETL 寫入。

## 前一階段：控制 Worker 初步需求檢查

- migration 023 保存每個 run 的初步檢查結果；只領取已確認且版本仍一致的輸入。
- 控制 Worker 經 PostgreSQL 原子領取、租約與背景 heartbeat 處理；租約失效停止提交，逾時留待人工核對，不自動重跑。
- 僅檢查需求文字、來源、目標 schema/table、無資料時的欄位以及明顯破壞性 SQL。這不是完整 SA 語意 Gate，不保證能偵測日期、Join 或寫入模式歧義。
- 缺漏結果為 `gate_result.status=NEEDS_INPUT`；run 暫停在 `NEEDS_REVIEW`，並保存欄位與原因。初步檢查通過仍為 `NEEDS_REVIEW / PIPELINE_NOT_READY`，絕不標示 ETL 成功。
- Task 頁顯示檢查原因與控制事件；目前補正表單與自動 revision 重跑尚未完成。取消未執行版本不會刪除其歷史檢查結果。
- 已在隔離 Compose 啟動 control-worker；API 與實際 ETL 執行開關仍為 false，不呼叫 AI、Hop 或 Vertica。API 的 worker_connected=false 仍指完整 ETL 執行尚未接通，並非控制服務健康檢查。
- 驗證：87 項後端回歸、13 項真實 PostgreSQL 整合、5 項瀏覽器流程。瀏覽器啟用控制 Worker 測試，確認核准後自動檢查、顯示暫停原因，並保留原 Task 資訊。
- 實際 Worker 日誌記錄測試 run `2d373b90-e322-498f-b593-4b663a32be1d` 為 CHECKED；API 證明 NEEDS_REVIEW 且 write_started=false。該合成版本已由測試取消，歷史保留。

### 控制 Worker 操作與測試

在 RockyLinux9 WSL 的 `/mnt/d/ChatGPT/ai_agents_v2` 執行：

```sh
docker compose -f deploy/compose.yml --profile pilot-control up -d control-worker
docker compose -f deploy/compose.yml logs --tail=30 control-worker
```

真實 PostgreSQL 回歸會暫時使用合成設定，必須先停止 control-worker，避免與測試領取者競爭；測試也會拒絕在其他 run 活躍時執行。完成後再啟動。不要啟用 execution profile 來繞過未完成的 ETL 閘門。

瀏覽器驗收先啟動控制 Worker，再於 frontend 設定 `WORKBENCH_TEST_CONTROL_WORKER=1` 執行 Playwright；這仍不是模型／Hop／Vertica E2E。

下一步：完成需求補正與新 revision 的閉環，再接 SA 結構化 contract；真實模型、Hop／Vertica、QA／Release、四案例及成果報告均未宣告完成。

## 前一階段：版本查閱與輸入確認

- 新增 migration 022，保存綁定 run／輸入 checksum／設定 checksum 的 INPUT_REVIEW 決定，不可覆寫。
- Task 畫面可建立「準備版本」、查看快照摘要與控制事件、確認或拒絕輸入、取消尚未執行的版本。
- 確認僅適用於輸入；不代表核准 Hop 寫入、QA 通過或 Release。
- 領取者只取得已確認輸入的 run。需求、Profile、Region、路由或 vault 機密版本改變後，舊確認不可沿用；重送舊确认亦回傳衝突。
- 領取前及寫入開始標記前再次比對目前版本；租約判斷使用 clock_timestamp，避免等鎖時間誤判。
- API 不回傳 worker lease token 或原始連線設定。Worker 仍未接通，不會因為確認輸入而開始 ETL。
- 最新結果：80 項後端回歸、11 項真實 PostgreSQL 整合、5 項瀏覽器流程通過；測試均不呼叫外部模型或執行 Hop。

### 本輪新增 API

| API | 行為 |
|---|---|
| POST /api/tasks/{id}/runs | 必須明確指定 mode=PREPARE 及 request_key；只建立準備快照，不派發 Worker |
| GET /api/tasks/{id}/runs | 查詢該 Task 的準備版本 |
| GET /api/tasks/{id}/runs/{run_id} | 查閱摘要、checksum、版本是否仍一致、輸入決定與控制事件 |
| POST /api/tasks/{id}/approvals | 只接受 INPUT_REVIEW，綁定指定 run 與兩個 checksum |
| POST /api/tasks/{id}/runs/{run_id}/cancel | 僅取消 QUEUED／NEEDS_REVIEW 且尚未標記寫入的版本；已開始寫入者拒絕直接取消 |

下列章節保留先前基礎實作紀錄；以本輪更新為最新狀態。

## 定位與範圍

- 內部 Pilot 優先，合成案例先行，固定流程控制 SA／Developer／QA 協作。
- 保留專案、原始 Task 設定、節點、Hop／SQL 與歷史資料。
- 不加入 Hermes、MCP Server、Agent framework、正式排程或多租戶。
- PostgreSQL 保存控制資料、Hop 執行 ETL、Vertica 為測試資料庫。

## 已實作

### 設定與模型邊界

- AI Profile 改用欄位編輯 Provider、Region、Endpoint 與角色路由，可取消、保存及重載。
- 既有模型呼叫改用共用 Gateway：缺少指定角色即失敗，不使用其他角色的模型代替。
- 直接 Bedrock 需指定 Region；LiteLLM Proxy 需指定 Endpoint 與 vault API key。
- Bedrock vault 機密格式為含 aws_access_key_id、aws_secret_access_key、可選 aws_session_token 的 JSON；未指定 vault reference 時使用部署環境 AWS credential chain。
- 機密只在模型呼叫時解密，不包含在 usage 回應；Profile 輸入驗證錯誤不回顯原始輸入。
- 暫時性模型錯誤最多重試兩次，JSON object 格式最多補正一次。角色業務 JSON Schema 尚待各角色 contract 完成。
- 模型測試 API 已改為真實呼叫，畫面須先接受用量；本輪沒有發出付費模型呼叫。
- Task 設定檢查顯示缺少路由／連線等阻擋原因；設定齊備只代表 CONFIGURED_NOT_TESTED。
- 解析器支援 Task override → Project → 平台預設；無有效設定則停止，不讀取開發機 Vertica 環境變數。
- 平台 PostgreSQL 由部署管理，網頁不可切換；連線一般設定拒絕明文密碼／API key。

### 執行佇列基礎

- 新增 migration 021：task_run、task_run_event 及快照不可變 trigger。
- enqueue 在同一交易鎖定 Task 與所引用設定，保存輸入及設定快照、checksum、Project 歸屬。
- 同 Task／request key 重送回傳原 run；相同 key 配不同 overrides 拒絕。不同 request key 不可建立第二筆 active run。
- 四個並行領取者使用 FOR UPDATE SKIP LOCKED，只有一個取得租約。
- heartbeat、寫入開始標記及完成操作皆須符合有效 lease token。
- 租約過期轉 NEEDS_REVIEW，不自動重排；舊領取者不可再完成或延長租約。
- 重新建立 Queue 物件仍可讀回同一執行結果；快照不能被 UPDATE，write_started 不能改回 false。

此佇列目前已接到 API 的準備與輸入確認流程，但尚未接真正 Worker／Hop。舊 Worker 尚未被替換；不宣稱完成 Worker 故障恢復或 exactly-once 外部寫入。

### 網站修正

- Task 保留原歷史詳情，新增可重新檢查的 Pilot 執行準備區。
- 模型角色與連線分欄，不再提供第二組可編輯模型路由。
- 修正有說明文字的欄位無障礙名稱、AI 測試區排版及窄版側欄 SVG 高度歸零問題。
- 全域四入口、Task 六頁籤與主管成果頁仍待實作。

## API 行為

| API | 目前行為 |
|---|---|
| GET /api/settings/ai-profiles | 讀取 Profile 清單，不回傳機密值 |
| PUT /api/settings/ai-profiles/{id} | 型別化更新，保留既有機密；只接受顯示名稱、Provider、Endpoint、Region、角色路由及 enabled |
| POST /api/settings/ai-profiles/{id}/secret | 加密保存，只回傳已設定狀態 |
| POST /api/settings/ai-profiles/{id}/test?role=... | 真實呼叫指定角色，可能計費；不再以設定存在代替連線成功 |
| GET /api/tasks/{id}/execution-settings | 無副作用設定檢查，不做連線測試，不授予執行權限 |

角色值為 requirement_gate、etl_specification、qa_review、file_understanding。
run 準備與 INPUT_REVIEW API 見本輪更新；執行／交付核准、完整 agent timeline、evidence／evaluation API 尚未接通。

## 最新驗證

- 後端回歸：76 passed（模型呼叫為替身測試，不是 AWS 成功證據）。
- 真實隔離 PostgreSQL：7 passed，涵蓋 4 個佇列測試及 3 個 migration 測試。
- Playwright：4 passed，涵蓋 AI Profile 編輯／取消／重載、專案 CRUD、Task 原始內容／8 節點／Job／返回、設定政策、Task readiness、窄版圖示與溢位。
- Web/API 已重建啟動於 http://127.0.0.1:5183，ETL execution 保持停用。
- 資料庫整合測試只清除自身建立的合成資料；連線設定完整還原。UI 測試建立的合成專案／Task 留在隔離 DB。
- 原 Windows DB 及歷史產物未迁移、覆寫或刪除。

## 接續順序與未驗收邊界

1. 獨立 Vertica Connection Profile 與真實連線測試；Task override 表單接線。
2. 完整階段狀態機、Specification／Execution／Release 核准、Worker heartbeat 與 Hop 子程序生命週期；未知寫入結果不得自動重跑。
3. 三角色 contract／handoff、compiler、真實 Hop → Vertica → QA → Release。
4. Task 六頁籤與四情境：正常、需求補正、Join 語意錯誤、執行缺欄位。
5. 20 案例評估、人工時間量測、成本帳本與主管報告。

目前單段 Specification 呼叫不等於三角色協作；模型測試 usage 僅回傳單次結果，尚未持久化至評估帳本。
舊執行器仍有環境設定依賴，resolver 尚未全面取代它。新佇列僅支援使用者準備與輸入確認，尚未連接真實執行派發。
未完成真實 Bedrock → Hop → Vertica → Release E2E；不可宣稱 Pilot 整體驗收完成。
