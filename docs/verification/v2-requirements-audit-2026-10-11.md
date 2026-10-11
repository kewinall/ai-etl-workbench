# v2 七階段操作改善：要求與證據對照

範圍：使用者提出的「階段導引＋進階詳情」、後續未完成項目修正與三個新的 CSV／Excel／LEFT JOIN 實際案例。它與 WS-0007 的完整 ETL 平台里程碑分開追蹤。JSON／資料表、REPLACE／UPSERT、已交付版本修正版、維運復原等仍是原已列明的獨立工作，沒有因本輪 UI 通過而完成。

起點：本機 `302c609`；5197 API source `7029156`、前端 source `d3a2e4d`（`index-CQpDjssy.js`）。原未提交 Join 測試保留，不納入本輪提交。下列「工程」表示程式與隔離驗證，不能替代真實模型／引擎／目標／交付證據。

最新：來源定位 `9860a5c` 已部署5197 web（`index-H2kR65yM.js`），API仍為`7029156`。定位8PASS，新三案與前一批三案各10PASS，完整隔離瀏覽器152PASS／28skip／0FAIL；八正式成果與九個其他服務不變。見 [部署證據](v2-field-focus-deployment-2026-10-11.json)。

後續最新：QA阻擋原因 `312e36c` 已部署5197 API/web（`index-D6-WBKU9.js`），相關後端57PASS、隔離及compiled授權瀏覽器各9PASS、新三正式成果唯讀10PASS。八Release與八其他服務不變；完整全套未另重跑。見 [QA部署證據](v2-qa-blockers-deployment-2026-10-11.json)。實際最新指引的新Task不可任意補證複核，不能降級指引或改保存證據制造資格；R19的新真實操作仍需合法前提。

| 編號 | 原要求 | 實作／驗證來源 | 判定與邊界 |
|---|---|---|---|
| R01 | 沿用 React／API／核准，不新增框架 | `frontend/package.json`；Run API 與既有 approval stores | 已沿用；此次來源定位修正不增加依賴 |
| R02 | 七階段與 Task／目前版本／狀態／最後更新 | `StageWorkspace.tsx`；`native-acceptance-delivery.spec.ts` | 5197 新三案與原三案的七階段查閱通過 |
| R03 | 共用 Run，網址保存階段、重載與返回 | `StageWorkspace.tsx`；`stage-guidance.spec.ts`；`run-detail-failure.spec.ts` | 工程通過；歷史／缺失版本不悄悄改成最新，真實版本查閱已回歸 |
| R04 | workflow-status 唯讀彙整、不另建可修改工作流 | `backend/app/workflow_status.py`；`test_workflow_status.py` | 已實作並部署；寫入仍由原交易重新驗證 |
| R05 | 現在在哪、完成什麼、誰處理、下一步 | `StageWorkspace.tsx`、`StageSummary.tsx`；`workflow-consistency.spec.ts` | 工程及正式交付查閱通過；不以百分比／預估時間代替資格 |
| R06 | 按鈕區分導覽與操作，阻擋時說明 | workflow `operation_qualifications`；`authorizationWorkspace`；操作稽核文件 | 已接資格與缺欄位預設停用；原證據入口的 23 項非下載資格已在實際 API 核對停用 |
| R07 | 服務離線時顯示未就緒，不假裝處理中 | workflow service projection；`qa-hop-authorization.spec.ts`；Worker presence | 工程離線分支通過；正常真實三案另有 Worker／model／Hop 證據，不外推所有停機／重開場景 |
| R08 | 操作後共用更新；5 秒 GET；頁面隱藏暫停 | `StageWorkspace.tsx`、`useWorkflowRefresh.tsx`；stage-guidance 輪詢測試 | 工程通過；真實三案執行至文件讀回有保存紀錄 |
| R09 | 讀取失敗標示過期、停用依賴資格 | stage workspace；settings／run／specification read-failure tests | 工程通過；不因 GET 失敗自動重送寫入 |
| R10 | 來源、轉換、目標、預期結果分組，以人可理解名稱為主 | `RunVersions.tsx`、`TransformationIntent.tsx`、`StageSummary.tsx` | 已有分組與來源 label；技術指紋保留進階區，仍須逐入口持續避免原始識別進入主要文案 |
| R11 | 缺漏定位來源／轉換／Join／目標，保留輸入 | `StageWorkspace.tsx`、`RunVersions.tsx`；stage-guidance 定位測試 | 本輪找出 CSV／來源欄位跳到空區塊；舊版新增測試 3 PASS／2 FAIL，修正後定位 8 PASS。只涵蓋既有允許編輯的來源，不擴張不可修改的實體契約 |
| R12 | Join 修訂、差異預覽、建立新版、不支援任意 SQL Join | `JoinInputEditor.tsx`；Run revision；stage-guidance Join 測試 | 已接 `join_contract_v1` 的雙來源等值 INNER／LEFT 規則，保留舊版及重新核准 |
| R13 | 儲存草稿／新版／核准／執行文案分開，失敗保留輸入 | RunVersions／useDraftGuard／operationLatch；settings、oracle、revision tests | 工程通過；本頁草稿不宣稱永久保存，離開／重載保護仍需遵循畫面提示 |
| R14 | SA／設計退回，修正先預覽再新版 | revisions／specification stores；三案真實 SA 紀錄 | 新 CSV 有真實 SA 退回及新版通過，未沿用舊核准；規格退回有工程分支，不宣稱另作了新版真實 Developer 退回 |
| R15 | 上游變更使下游核准失效，不能沿用 | queue/context binding、SA/spec guards；write-refusal tests | 隔離有效／缺少／失效／跨 Run 驗證與新版本流程通過 |
| R16 | 本版命名契約，不混入目前 Task／歷史命名 | naming read／input summary；naming／run history tests | 程式沿用版本綁定；真實交付及歷史版本查閱保留 |
| R17 | 執行前看目標、副作用、固定答案與資格 | Hop／Oracle UI及 transactional stores；三案 native proof | 三新案例正常網站與實際 Hop／Vertica，事前固定答案為 2／2／5 筆，不從結果反推 |
| R18 | 執行結果、節點、筆數、差異、失敗原因自動讀回 | RunArtifacts／HopDispatch／ComparisonHistory；native readback proof | 正常三案真實節點、固定答案 MATCH、獨立 SELECT 通過；異常顯示另有工程及保存歷史證據 |
| R19 | QA 意見、人工核准；缺同次證據只重新審查、不重跑 Hop | qa journal／authorization；QA reassessment UI test；retained-history proof | 工程補證 body／一次预約通過，原真實 NEEDS_REVIEW→PASS 兩紀錄與新 UI 查閱通過；**尚未另作新版真實補證操作** |
| R20 | 已執行流程修正保留原結果，用新目標與重新核准 | Run revision／qa revision；stage-guidance／recovery-history tests | 工程修正版分支與保存真實失敗／修正歷史有證據；**本輪未新增真實失敗後修正版全鏈**。已交付版本修正版仍明示不支援 |
| R21 | 失聯／可能部分寫入顯示待核對，不提供一般重試 | ExecutionReconciliation／準備結案；owner-death、partial、retained-history proofs | current 控制面死亡與真實 PG 網站結案通過；原真實部分提交／失聯的 current UI 唯讀通過；**尚未另作新版 Hop 部分提交與結案** |
| R22 | 網路斷線／回應遺失先 GET；雙擊不重送模型／執行 | latches／request keys；comparison／QA／Hop／SDM response-loss tests | 工程分支通過、警示不被背景 GET 清除；不把合成回應遺失當真實服務故障 |
| R23 | SDM、候選包、可攜驗證、正式 ZIP及 manifest 文件清單 | SdmDelivery／release stores；delivery／portability proofs | 三新案例真實 QA／SDM／獨立可攜 DB／正式 ZIP，下載及成員指紋一致；產物自動讀回修正已部署 |
| R24 | 歷史與舊證據收合，空白舊區不顯示 | LegacyTaskRecords；legacy/history tests | 已完成條件收合與空節點停止新建；舊資料／下載保留，沒有順便刪資料 |
| R25 | 專案清單共用狀態與接續精確 Run／階段 | Project UI／summary projection；workflow consistency | 工程與真實交付摘要讀回通過；讀取失敗顯示待確認 |
| R26 | 旧網址相容、移除沒使用舊功能而保留證據 | main routes；retired Task POST 410；legacy UI/API tests | 舊入口／無引用元件及覆寫已退場；部分歷史 GET 明確保留，不能把歷史讀取當未刪舊功能 |
| R27 | 390／768／1440 與鍵盤完成主要流程 | stage-guidance／native acceptance tests；compiled deployment proofs | 三寬度查閱／下載、工程表單／定位通過；**真實三案寫入流程主要在1440，不宣稱三寬度都重做真實寫入** |
| R28 | 5197 独立設定與實際 Profile，不動 5183 | compose.ui-acceptance、local Worker target config；three-case model proof | 5197 原／可攜資料隔離、真實 LOCAL_COPILOT 模型；一次秘密移轉已完成，不重複使用授权 |
| R29 | CSV／Excel／LEFT JOIN 三個新正常七階段案例 | native／delivery／portability 2026-10-11 proof | 三案實際通過，原寫入各一次；未將 JSON／資料表來源標示全鏈完成 |
| R30 | 舊 Release 唯讀回歸，指紋與寫入次數不變 | release-regression helper；API／web deployment proofs | 八個正式成果持續 GET 核對，原 ZIP／完整 Run／Release／updated／WRITE_STARTED 不變；没有重跑 |
| R31 | 分段提交、WS-0007、證據及下一步 | 本機 commits；CURRENT/tasks/handoff讀回 | 階段來源與證據已推送 `kewinall/ai-etl-workbench` main `5e63367`，遠端SHA與本機一致；原未提交Join測試與私人runtime證據未納入。WS-0007仍進行中，不把階段上版當整體完成 |

## 下一個處理順序

1. 此次定位full browser/build、5197 web-only部署與既有成果回歸、文件首頁及階段來源上版均已完成。
2. 對 R19／R20／R21／R27 的新操作證據缺口，依 [下一批範圍](v2-next-native-acceptance-scope-2026-10-11.md) 準備具體獨立案例與固定答案、測試安全前提及需要的模型／引擎核准。三個已交付案例的代理授权不擴張為任意新目標寫入；不能重放已交付／已結案案例來補證。

不重新把上表正常三案、舊文件下載或已通過唯讀查閱當作「新的故障／補證」；整體 v2／WS-0007 維持部分完成。
