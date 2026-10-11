# v2 功能收斂、狀態修正與操作精簡（2026-10-11）

## 最新結論

> 第二輪 Codex 核查補正見文末「第二輪」；以下為第一輪紀錄（部分說法已在第二輪更正）。

三段工程修改已完成，並經使用者授權以 `--no-deps` 只重建 5197 的 api／web（`84c0fc5`）；**未推送 GitHub**。
5197 GET-only 讀回：專案摘要 `可交付 3`、三案七階段 `can_operate` 全 false、只剩 `release_download`；
21 個階段頁無可用寫入按鈕或勾選框；部署前後 ZIP SHA-256、`updated_at`、WRITE_STARTED 次數均不變。
證據：[5197 讀回](ui-simplification-5197-readback-2026-10-11.json)。
5183 未升級，已交付三案（TASK-20261010-0017／0018／0019）未重跑、未寫入。

| 分段 | Commit | 內容 |
|---|---|---|
| 1 狀態修正 | 見 Git log：`fix: unify workflow status, per-operation eligibility and project summary` | 逐操作資格、milestones／effective_status、專案摘要共用彙整、已交付只讀 |
| 2 介面精簡 | `feat: simplify seven-stage workspace around summaries and one refresh` | 七階段摘要、完成階段收合、正式交付文件清單、單一重新核對、窄版階段清單、工作清單優先 |
| 3 遺留整理 | `refactor: remove unreachable legacy UI and make overrides explicit` | 移除 3 個舊元件、main.tsx 多代覆寫與無入口實作、更新文件 |

起點：本機 `ad61c9f`。既有未提交的 `backend/tests/test_join_replay_worker.py` 修改保留，未混入本輪提交。

## 1. 狀態與操作資格

- `GET /api/tasks/{task}/runs/{run}/workflow-status`（新增欄位，舊欄位保留）
  - `operation_qualifications`：`prepare_run`、`input_confirm`、`input_cancel`、`requirement_revision`、
    `sa_authorize`、`sa_approve`、`naming_confirm`、`developer_authorize`、`specification_create`、
    `specification_approve`、`oracle_save`、`oracle_approve`、`hop_execute`、`execution_close`、
    `comparison_recovery`、`qa_authorize`、`qa_approve`、`sdm_prepare`、`release_candidate`、
    `release_approve`、`release_download`。每項 `type`／`enabled`／`blocked_reason`；需 Worker 者另有 `service_ready`。
    舊的 `sa`／`developer`／`qa`／`hop`／`portability` 服務項目保留。
  - 資格只由既有 offer、核准、綁定與服務心跳彙整，**不新增可修改的工作流狀態**；所有寫入 API 的後端驗證不變。
  - `milestones`（input_confirmed、sa_approved、specification_approved、execution_started、executed、qa_approved、delivered）、
    `effective_status`、`delivered`、`source_types`；`source_scope_note` 依實際來源類型。
  - 已交付 Run：七階段 `can_operate` 全為 false（僅提示），所有寫入資格停用，原因「此版已正式交付；只能查看與下載…」；只有 `release_download` 可用。
- `GET /api/projects/{id}/summary`：保留 `states`、`qa_evaluated`、`release_evaluated`（原語意）；新增 `workflow_counts`、`tasks[]`
  （`task_id`、`run_id`、`category`、`current_stage`、`next_action`、`effective_status`、`delivered`、`waiting`、`stale`）、
  `workflow_unverified`、`workflow_evaluated`。單一 Task 讀取失敗記為「待確認」且 `stale=true`，不當成零筆或完成。
- `GET .../release`：`release.documents` 由已保存的 Release manifest `artifacts` 產生，不依檔名推測。

前端：專案摘要、篩選與 Task 卡片共用 `/summary` 的工作流程結果；需求頁「當時執行紀錄」與「目前有效狀態」分開；
QA 頁模型紀錄標示「模型建議已通過格式驗證（人工核准另列）」，人工核准以有效核准為準。
REPLACE／UPSERT 在補正表單中不可選為新版執行方式，只保留既有版本的歷史意圖。

## 2. 介面

- 固定區：專案名稱、Task、「第 N 版（最新／歷史）」、目前有效狀態、更新時間；UUID／checksum 收進「技術識別」。
- 每階段先顯示唯讀摘要；已完成階段的完整元件、歷史與技術內容收合（未展開時不掛載、不讀取）。
- 成果交付：已交付先顯示正式 ZIP 下載與 manifest 文件清單；候選 SDM、候選包與可攜驗證收進「候選文件、可攜驗證與交付歷史」。
- 工作區只保留「重新核對狀態」；元件刷新按鈕只在該區 GET 失敗時以「重試讀取…」出現。
- 問題位置以來源名稱／左右表／欄位名稱顯示，精確路徑收合；修訂差異以欄位原值／新值呈現，原始 JSON 收合。
- ≤600px：「目前查看：第 N 階段」＋可展開七階段清單；較寬畫面保留七階段導覽。sticky 標頭加 `scroll-padding-top`。
- `index.html` 補 `meta viewport`：5197 實測發現手機模擬時版面退回 980px 桌面寬度（原本即缺），補上後以 `isMobile` 測試驗證 390px。
- 專案預設進入「工作清單」；專案切換收合；「專案設定」「Pilot 評估」歸於「管理」。`/projects/{id}/settings`、`/evaluation` 舊網址仍可開啟。

## 3. 引用稽核與移除

工具（只讀）：`node scripts/frontend-reachability.mjs frontend`、`python3 scripts/main_tsx_reachability.py frontend/src/main.tsx`。
檢查 import／export、`import()` 動態載入（無）、routes、tests（無 import 這些元件）、CSS class 使用與外部下載 API。

| 類別 | 項目 | 處理 |
|---|---|---|
| 目前使用 | `main.tsx` → `StageWorkspace.TaskWorkspace`、`ProjectWorkspace` 等 81 個靜態可達模組 | 保留 |
| 相容導向 | `#/dashboard`、`#/usage`、`#/models`、`#/database`；舊 Task tab `overview/collaboration/artifacts/execution`；`/projects/{id}/settings`／`evaluation` | 保留 |
| 歷史證據 | `LegacyTaskRecords`（舊版節點／Log／Hop／SQL 下載）、所有後端相容 API、Task／Run／模型紀錄／ZIP／核准 | 保留，不刪資料 |
| 無引用 | `workbench/TaskWorkspace.tsx`、`ExecutionReadiness.tsx`、`DeliveryStatus.tsx`（入口不可達、無測試或動態載入） | 已移除；專屬 CSS `.wb-task-heading`、`.wb-task-tabs`、`.wb-timeline` 一併移除。**第二輪更正**：`ExecutionReadiness`（Pilot 執行準備）與可讀的版本協作時間軸只存在於已失效的 TaskWorkspace，移除後功能實際消失；已在七階段工作區恢復（見下方第二輪） |
| 無引用 | `main.tsx` 53 個不可達宣告（舊 Dashboard、Analyzer、多代 Projects／Settings／Wizard／TaskDetail 等）與 10 條 runtime 覆寫（7 個名稱） | 已移除；`Usage`→`LayeredModelUsage`、`SystemSettings`→`CompleteFieldSettings` 改為明確引用 |

`main.tsx` 由 194,950 bytes 降為約 49.6 KB；不再有 `@ts-ignore` 覆寫（原本 `SystemSettings=OperationalSystemSettings` 一類覆寫會被 `@ts-ignore` 隱藏型別錯誤）。
~~移除元件呼叫的 API 均仍由現行元件使用~~ **更正（第二輪）**：此說法不正確。`GET /api/tasks/{id}/execution-settings`（Pilot 執行準備）與可讀協作時間軸在移除後沒有任何現行畫面使用，等於功能遺失；已恢復。後端相容 API 未變更。

## 測試與證據

| 類型 | 命令 | 結果 |
|---|---|---|
| 後端單元＋隔離 PostgreSQL（非 5197） | `pytest backend/tests`（compose.p0-tests 等效環境變數） | 基準 `ad61c9f`：2038 passed／129 skipped；本輪：2048 passed／129 skipped（+10 新測試，0 failed） |
| 真實讀回離線重放 | `tests/test_workflow_status_native_readback.py` | 3 passed；值取自 5197 GET-only 讀回（2026-10-11） |
| 前端 build | `npm run build` | PASS |
| 瀏覽器（隔離本地 API＋合成路由） | `npx playwright test` | 基準 `ad61c9f`：54 passed／22 failed／36 skipped；本輪完整回歸：63 passed／22 failed／36 skipped。22 項失敗清單與基準逐項相同（基準即失敗的舊測試），本輪未新增失敗 |
| 新增一致性測試（合成 API） | `tests/workflow-consistency.spec.ts` | 摘要／篩選／卡片一致、已交付七階段無修改操作、摘要失敗顯示待確認、390／768／1440 無橫向溢出與 console error |

類型說明：上述瀏覽器測試是 **合成 API／隔離本地 API**，不是 5197 真實 API；本輪 **沒有** 真實 ETL、模型呼叫或 Release 寫入。

## 尚未完成

1. （已完成）5197 api／web 部署與 GET-only 讀回；control、Hop／可攜驗證服務、volumes 與 5183 未重建。新操作（退回、補證、修正版、失聯結案）尚未在 5197 實測。
2. 已交付版本「建立修正版」：後端目前只允許需求缺口、QA 退回、失敗結案三種修正版；已交付 Run 無法從原版建立修正版，畫面明示「只能查看與下載」。是否開放需另行決策。
3. Codex 獨立驗證清單（見交接文件），包含退回／補證／修正版／失聯結案與 GET 下載回歸。
4. JSON／資料表完整執行、REPLACE／UPSERT、維運復原、完整列印報告、人工成效基準：另列里程碑，不因本輪宣稱 v2 完成。

## 回復方式

見文末「第二輪：回復步驟」（含確切 commit、viewport 修正與 5197 部署設定）。

---

## 第二輪：Codex 獨立核查補正（2026-10-11）

起點：本機 `146e963`（即 5197 目前部署內容）。本輪 **未部署 5197、未推送 GitHub、未改 5183、未重跑已交付目標、未替換固定答案**。

| Commit | 內容 |
|---|---|
| `188dfe7` | 資格缺漏時停用：受管理工作區缺 `operation_qualifications`、缺單項、`enabled` 非布林 `true`、或回應 Run 不一致時，寫入停用並顯示「操作資格尚未確認」；舊元件在非受管理環境保留相容（無寬鬆 fallback 進入正常工作區）。後端補 `sa_cancel`、`sdm_candidate`、`preparation_close` 與 task 層級 `prepare_run`／`input_cancel` |
| `2ce20c9` | 真正的管理入口：主導覽只留「專案工作區」「操作指南」與可展開「管理」（專案設定、Pilot 評估、Pilot 成果、平台設定中心）；`aria-expanded`、Enter／Space、Esc 收合並回焦點；舊網址 `#/projects/{id}/settings`、`/evaluation`、`#/system`、`#/pilot`、`#/usage` 仍可開啟並自動展開管理 |
| `b875ecf` | 退回／失效／已取消最新版的狀態：Gate 退回（`needs_input`）不再把第 1 階段標「已完成」；`stale_latest`、`cancelled_latest` 回到需求階段並給可執行下一步；已交付阻擋原因不再指向不存在的修正版操作 |
| `c11832a` | 恢復 Pilot 執行準備與可讀版本協作時間軸；唯讀 POST（compile-preview、validate、naming suggest）不觸發整頁重新讀取；版本操作成功訊息在切換版本後保留；已交付版本顯示「目前不能直接從已交付版本建立修正版」；操作指南同步 |
| `9502e67` | 22 項失敗測試逐項處理（下表） |
| `5745ba0` | 已失效的退回版本：有效狀態改為「內容已變更，此版不可沿用」，與「取消此版並建立新準備版本」一致，不再邀請就地補正 |

### 22 項失敗測試分類與處理

分類：**產品缺陷**＝畫面行為錯誤，已修正後重驗；**舊測試**＝走已移除入口（舊分頁、各區「重新載入版本」、未收合區塊）或合成資料不完整，改走目前階段與收合入口，保留原業務斷言；**環境前置**＝需改寫平台設定或 CONTROL Worker，改為明確 opt-in 並在測試內檢查前置。沒有以刪除測試、弱化斷言或無理由 skip 消除失敗。

| # | 測試 | 失敗原因 | 分類 | 處理結果 |
|---|---|---|---|---|
| 1 | ai-profile-drafts | 合成 profile 缺 `updated_at`／版本，產品正確拒絕保存 | 舊測試（fixture） | fixture 補版本欄位，新增 `X-Settings-Version` 標頭斷言；通過 |
| 2 | excel-contract-live | (a) 改寫平台設定；(b) Gate 退回後第 1 階段被標「已完成」且需求區收合；(c) 補正須先預覽差異（b5f48fd 既有流程） | 產品缺陷＋環境前置＋舊測試 | `b875ecf` 修狀態；`WORKBENCH_ALLOW_SYNTHETIC_UI=1` opt-in；補「預覽修訂差異→勾選確認」步驟，原等待鎖定與回讀斷言保留；通過 |
| 3 | excel-selection-live | 走舊 Task 頁與未收合的設定區 | 舊測試 | 改走 `/requirements` 與「Task 保存設定」收合區；通過 |
| 4 | json-confirmation-live | 同 #2；另外規格建立在七階段 UI 要求 SA 核准，而本隔離環境不呼叫模型 | 產品缺陷＋環境前置＋舊測試 | 同 #2；SA 證據改在需求審查階段「需求審查技術證據」；設計階段僅以路由覆寫 SA 前置（`can_operate`、`specification_create`），JSON 綁定／規格核准／SDM／編譯預覽仍打真實隔離 API；通過 |
| 5 | oracle-history | 舊分頁與重試按鈕；390px 需先展開階段清單 | 舊測試 | 改走執行確認／執行與結果階段；通過 |
| 6 | project-history-filter | 篩選改用 `/summary` 工作流程分類；strict-mode 重複文字 | 舊測試 | fixture 提供 summary tasks，篩選「需修正」；通過 |
| 7 | project-workspace（CRUD） | 專案分頁移除、切換器收合 | 舊測試 | 改走工作清單與收合切換器；通過 |
| 8 | project-workspace（歷史 Task） | 舊版節點檢視入口改為「舊版紀錄」 | 舊測試 | 改斷言 `aria-pressed` 與「舊版節點詳情」區；節點內容斷言保留；通過 |
| 9–13 | qa-source-formats ×5 | 以連接埠判斷環境，在本地隔離 API 誤判 | 舊測試（前置判斷） | 改以 `/api/ready.execution_enabled=false` 為前置，走品質審查階段；通過 |
| 14 | readiness-response | Pilot 執行準備面板只在已移除的 TaskWorkspace | 產品缺陷 | `c11832a` 恢復面板；測試未修改；通過 |
| 15 | run-detail-failure | 版本選擇改為標頭共用選單 | 舊測試 | 改用「共用 Run 版本」與 alert 斷言；通過 |
| 16 | run-versions | 舊版本清單／各區刷新；成功訊息切換版本後消失；已取消／失效最新版無路可走 | 產品缺陷＋舊測試 | `c11832a`／`b875ecf` 修正；改用單一「重新核對狀態」與時間軸；CONTROL 分支 opt-in（`WORKBENCH_TEST_CONTROL_WORKER=1`）亦已通過 |
| 17 | source-evidence | 舊入口與刷新按鈕 | 舊測試 | `routeWorkflow` fixture＋「重新核對狀態」；通過 |
| 18–20 | specification-history V1／V2／V4 | 編譯預覽被唯讀 POST 觸發的整頁刷新清除；舊入口 | 產品缺陷＋舊測試 | `c11832a` 唯讀 POST 豁免；改走設計階段；通過 |
| 21 | tool-load-failure | 合成回讀缺版本欄位 | 舊測試（fixture） | fixture 補版本並加標頭斷言；通過 |
| 22 | transformation-intent | 需 CONTROL Worker 才會進入 NEEDS_REVIEW；舊「重新載入版本」；補正須先預覽差異 | 環境前置＋舊測試 | opt-in（`WORKBENCH_TEST_CONTROL_WORKER=1`＋`WORKBENCH_ALLOW_SYNTHETIC_UI=1`）；改用「重新核對狀態」與差異預覽；通過 |

另外：`stage-guidance` 2 項在恢復 Pilot 執行準備後因合成 API 未回應 `/execution-settings` 出現第二個 alert（strict mode）；已在 fixture 補完整回應，未放寬斷言。

### 本輪測試結果（雲端隔離環境；非 5197）

| 類型 | 環境 | 結果 |
|---|---|---|
| 後端單元＋隔離 PostgreSQL | `pytest backend/tests`（compose.p0-tests 等效變數） | 2052 passed／129 skipped（第一輪 2048） |
| Playwright 預設（合成 API＋隔離本地 API，無 opt-in） | `npx playwright test` | **89 passed／0 failed／39 skipped**（第一輪 63／22／36）。新增 3 個 skip 為 #2、#4、#22 的明確 opt-in |
| Playwright opt-in：CONTROL Worker | 本地隔離 API＋`python -m app.control_worker`（`WORKBENCH_CONTROL_WORKER_ENABLED=true`、execution／模型派發全關） | transformation-intent、run-versions（含 CONTROL 分支）2 passed |
| Playwright opt-in：控制單次（不常駐 Worker） | `WORKBENCH_CONTROL_PYTHON` 指向本地 venv | excel-contract-live、json-confirmation-live 2 passed（連續 3 次） |
| 截圖 | 390／768／1440 | 管理群組展開、Gate 退回後需求頁（私人證據，未入 repo） |

類型界線：全部是 **合成 API 或隔離本地 API／PostgreSQL**；**沒有** 真實模型呼叫、Hop／Vertica ETL 或 Release 寫入；不等於 5197 Runtime 驗收。

opt-in 執行前置：
- 只在隔離 DB 執行；不可對 5197／5183 使用。
- excel／json live 的控制腳本拒絕領取其他 Run：若 DB 已有其他「已核准 QUEUED」Run 會直接失敗（實測：預設全套跑完後殘留 1 筆，先跑 CONTROL Worker 組消化後才通過）。
- `claim()` 使用 `SKIP LOCKED`；頁面讀取規格歷史時 `GET .../specifications` 會短暫鎖 Task 列，控制腳本因此最多重試 20 次（實測重試 1 次）。這是既有後端行為，非本輪修改。

### 已交付版本限制（維持，不新增能力）

已交付版本只能查看與下載。目前 **不能** 從已交付版本建立修正版或新的準備版本；畫面固定顯示此限制，不提供不存在的操作指引。是否開放需另行決策。

### 未完成與已知限制

1. 本輪修正 **尚未部署 5197**（5197 仍為 `146e963` 內容）；部署需使用者另行授權，沿用 `runtime-temp/claude-2026-10-11/deploy-5197.cmd`。
2. 操作資格只是前端停用與後端唯讀彙整；後端寫入 API 未依新資格拒絕。例：規格建立 API 不要求 SA 核准（json live 測試即利用此點），已交付 Run 的寫入也未實測「直接呼叫 API」是否被拒。
3. 退回／補證／修正版／失聯結案的新分支僅有合成或隔離測試，尚未在 5197 實測。
4. 39 個 skip 中其餘 36 個為既有 opt-in（真實案例、真實 Worker、Copilot、保留證據）或「Requires existing navigation」類舊 skip，本輪未處理。
5. JSON／資料表完整執行、REPLACE／UPSERT 執行、維運復原、完整列印報告、人工成效基準仍為獨立里程碑。

### 第二輪：回復步驟

程式回復（在 `D:\ChatGPT\ai_agents_v2`，Windows 端加 `-c core.autocrlf=true`）：

| 目標 | 指令 |
|---|---|
| 回到 5197 目前部署內容（撤銷第二輪） | `git revert --no-edit HEAD 5745ba0 9502e67 c11832a b875ecf 2ce20c9 188dfe7`（新到舊；`HEAD` 指本文件所在的 `docs: record Codex review corrections` commit，若之後另有提交請改用該 SHA）；結果等同 `146e963` |
| 撤銷全部 UI 收斂但保留手機 viewport 修正 | 再依序 revert `146e963 99fa153 1336da7 1adf3dd`，**跳過 `84c0fc5`**（index.html `meta viewport`；撤銷會讓手機退回 980px 版面） |
| 完全回到起點 | 回到 `ad61c9f` 內容（含撤銷 `84c0fc5`） |

不涉及 migration 或資料修改；API 只新增欄位，舊前端仍可讀。

部署回復（僅在已部署新版且需回復時；需使用者授權）：checkout 目標內容後重跑
`docker compose -f deploy/compose.stage-guidance.yml -f deploy/compose.ui-acceptance.yml up -d --no-deps --build api web`
（`UI_ACCEPT_PROJECT_ID=346e9419-4b0e-4ba7-ad29-1756ca7da833`，即 `deploy-5197.cmd`）。只重建 api／web；control、postgres、Hop／可攜驗證服務、volumes、5183 不動；完成後以 GET-only 讀回三案 ZIP SHA-256、`updated_at`、WRITE_STARTED 次數確認不變。

## 第三輪：Codex 第二輪核查補正（2026-10-11）

起點 `400b95b`（Codex 驗證結果：規格 V1／V2／V4 19 passed／3 failed、時間軸舊文案、規格 API 不要求 SA）。本輪仍 **未部署、未推送**；5197 仍為 `146e963`；5183 未動；未執行模型、Hop、Vertica 或 Release 寫入。既有未提交的 `backend/tests/test_join_replay_worker.py` 修改保留、未納入任何 commit。

| Commit | 內容 |
|---|---|
| `d68755b` | 後端：規格保存／核准需要同一 Run 目前有效的 SA 人工核准 |
| `d44d92d` | 前端：規格頁背景讀取不清除操作回饋；忽略過期回應；編譯預覽依內容指紋保留 |
| `7ac2222` | 前端：時間軸文案改為當時事件事實；接入共用刷新，正常隱藏刷新按鈕、失敗才提供重試 |
| `edc0985` | 測試：JSON live（opt-in）改用合成 SA 核准，不再覆寫畫面資格 |

### 1. 規格操作回饋與編譯預覽（`d44d92d`）

- 背景讀取（共用「重新核對狀態」、寫入後重讀）與使用者操作分開：背景讀取不清除成功訊息、操作錯誤或仍有效的編譯預覽；背景讀取失敗只顯示錯誤與「重試讀取規格版本」，保留上次內容。
- 只套用最新一次規格清單讀取；較早的讀取或前一個 Run 的回應晚到時忽略。
- 編譯預覽以「Run＋規格 ID＋內容指紋＋可核准狀態」為鍵：不變時保留；切換版本／Run 或內容改變才清除；預覽請求回來時若顯示內容已不同則丟棄。
- 保存或核准成功後先顯示成功訊息，再重讀；重讀失敗不會掩蓋已成功的寫入。
- 新增 `specification-refresh-race.spec.ts`（6 項）：以 gate 控制回應順序，不用固定等待；涵蓋背景重讀晚於／早於 onSaved、較早讀取晚到、預覽保留與清除、切換 Run、背景讀取失敗。**對 `400b95b` 的元件執行為 1 passed／5 failed**（僅切換 Run 一項舊版也通過），新版 6 passed。原 V1／V2／V4 測試斷言未修改。

### 2. 時間軸（`7ac2222`）

- `PIPELINE_NOT_READY` 顯示「當時初步需求檢查完成，等待後續審查」；原事件代碼仍在技術行，不由舊代碼推論目前服務狀態。
- 時間軸原本位於共用刷新 context 之外，固定顯示自己的按鈕。現包入 managed context，隨「重新核對狀態」重讀（只套用最新讀取，重讀期間保留舊紀錄）；正常狀態不顯示按鈕，讀取失敗才出現「重試讀取此版本紀錄」（可鍵盤操作）。工作區外仍保留手動按鈕。
- 新增 `collaboration-timeline.spec.ts`（已交付／未交付各 1）：文案、原代碼、正常無按鈕、共用刷新、失敗保留紀錄＋鍵盤重試、390px。對 `400b95b` 執行 2 failed，新版 2 passed。

### 3. SA 前置條件（`d68755b`）

- `POST /specifications` 與 `POST /specifications/{id}/approve` 在既有 Task 鎖、同一交易內，於任何寫入前（含語意拒絕證據）檢查：本 Run 有 `sa_handoff_approval`，且其 binding 等於以目前輸入、設定、SA context 與 review 重新計算的 binding。沿用既有核准資料，不新增工作流狀態。
- 拒絕：HTTP 409，`detail.code` 為 `SPEC_SA_APPROVAL_MISSING`（無核准，含他 Run 核准）或 `SPEC_SA_APPROVAL_STALE`（已失效），`detail.message` 為中文原因；不新增規格、核准或事件。
- `validate`／`compile-preview` 與歷史 GET 不變（未加 SA 條件）。
- `workflow-status`：`specification_approve` 同步要求 `sa_ok`（`specification_create` 原已要求）。
- Developer journal 內部保存（`developer_journal.finish`）未加此檢查：Developer 預約時已要求 SA 核准；若之後 SA 失效，規格核准 API 仍會拒絕。
- 測試：新增 `test_specification_sa_prerequisite_integration.py`（缺 SA 含語意錯誤提案不留證據、有效 SA 冪等保存與核准、SA 失效拒絕核准與保存且保留歷史、他 Run 核准不適用、已寫入仍拒絕）與 `test_workflow_status.py` 參數化 3 項。
- 既有測試調整（因新規則，非放寬）：共用 fixture `prepared()` 預設以合成 SA review＋既有人工 SA 核准（無模型呼叫）取得前置條件，自行測 SA 流程的測試改為 `sa_approved=False`；`test_upstream_change_invalidates...` 的最後一次保存改斷言 409 `SPEC_SA_APPROVAL_STALE`（原為語意 INVALID）；`test_source_order_api...` 的 invocation 計數排除 fixture 的合成 SA；fixture teardown 以 `session_replication_role=replica` 刪除自己建立、受不可變 trigger 保護的合成 SA 核准列（僅測試清理）。

### 測試結果（雲端隔離環境；非 5197）

環境：本地 PostgreSQL 16（compose 為 17）、Python 3.12 依 `constraints-linux-py312.txt`、隔離 API（獨立 DB、模型／Hop／QA 派發關閉、`WORKBENCH_ARTIFACT_ROOT` 指向暫存目錄）、Vite 5199 代理、預裝 Chromium。skip 數與 Docker compose 環境不同，不宣稱與 Codex 數量相等。

| 類型 | 起點 `400b95b` | 本輪 HEAD |
|---|---|---|
| 後端 `pytest backend/tests` | 2061 passed／128 skipped | **2069 passed／128 skipped**（+8 新測試，0 failed） |
| Playwright 預設 | 未在本環境重跑（Codex：選定 22 項 19／3） | **97 passed／0 failed／39 skipped**（第二輪 89＋新增 8） |
| Playwright opt-in：控制單次＋合成寫入 | — | json-confirmation-live、excel-contract-live **2 passed，連續 3 次** |
| Node 單元 `node --test tests/*.test.mjs` | — | 6 passed |
| `npm run build`、`git diff --check` | — | PASS |

類型界線：全部為合成 API 或隔離本地 API／PostgreSQL；沒有真實模型、Hop／Vertica 或 Release；不等於 5197 Runtime 驗收。

### 第三輪仍未完成

1. 未部署 5197、未推送；待 Codex 獨立驗證後由使用者決定。
2. `specification-live.spec.ts`（opt-in）仍使用已移除的舊入口，且未取得 SA 核准；新規則下需改用 `syntheticSaApproval()` 並改走七階段頁，本輪未處理。
3. 其他寫入 API（例：已交付 Run 的直接寫入）仍未逐一實測後端拒絕；本輪僅處理規格保存／核准。
4. 已交付版本不能建立修正版（維持）；JSON／資料表完整執行等仍為獨立里程碑。

### 第三輪：回復步驟

| 目標 | 指令（Windows 端加 `-c core.autocrlf=true`） |
|---|---|
| 撤銷第三輪全部 | `git revert --no-edit <本文件 commit> edc0985 7ac2222 d44d92d d68755b`（結果等同 `400b95b`） |
| 只撤銷後端 SA 規則 | `git revert --no-edit edc0985 d68755b`（JSON live 測試須同時撤回，否則仍會建立合成 SA） |

不涉及 migration 或資料修改。部署回復沿用第二輪的 api／web 重建命令（需使用者授權）。
