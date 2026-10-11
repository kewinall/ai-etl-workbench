# v2 功能收斂、狀態修正與操作精簡（2026-10-11）

## 最新結論

三段工程修改已在隔離環境完成並驗證；**尚未部署 5197、未推送 GitHub**。
狀態一致性已用 5197 真實讀回值離線重放驗證（不是部署驗收）。
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
| 無引用 | `workbench/TaskWorkspace.tsx`、`ExecutionReadiness.tsx`、`DeliveryStatus.tsx`（入口不可達、無測試或動態載入） | 已移除；專屬 CSS `.wb-task-heading`、`.wb-task-tabs`、`.wb-timeline` 一併移除 |
| 無引用 | `main.tsx` 53 個不可達宣告（舊 Dashboard、Analyzer、多代 Projects／Settings／Wizard／TaskDetail 等）與 10 條 runtime 覆寫（7 個名稱） | 已移除；`Usage`→`LayeredModelUsage`、`SystemSettings`→`CompleteFieldSettings` 改為明確引用 |

`main.tsx` 由 194,950 bytes 降為約 49.6 KB；不再有 `@ts-ignore` 覆寫（原本 `SystemSettings=OperationalSystemSettings` 一類覆寫會被 `@ts-ignore` 隱藏型別錯誤）。
移除元件呼叫的 API 均仍由現行元件使用，後端相容 API 未變更。

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

1. 部署至 5197（需保留 `compose.stage-guidance.yml`＋`compose.ui-acceptance.yml`、`UI_ACCEPT_PROJECT_ID` 與保管庫掛載），部署後以 GET-only 對三案逐階段讀回、截圖與 ZIP 指紋比對。
2. 已交付版本「建立修正版」：後端目前只允許需求缺口、QA 退回、失敗結案三種修正版；已交付 Run 無法從原版建立修正版，畫面明示「只能查看與下載」。是否開放需另行決策。
3. Codex 獨立驗證清單（見交接文件），包含退回／補證／修正版／失聯結案與 GET 下載回歸。
4. JSON／資料表完整執行、REPLACE／UPSERT、維運復原、完整列印報告、人工成效基準：另列里程碑，不因本輪宣稱 v2 完成。

## 回復方式

依序 `git revert` 三個 commit（3→2→1）。API 只新增欄位，舊前端仍可讀；不涉及 migration 或資料修改。
