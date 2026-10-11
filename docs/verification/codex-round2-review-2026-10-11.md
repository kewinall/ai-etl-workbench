# Codex 第二輪獨立驗證（2026-10-11）

## 結論

核查本機 `400b95b`。不接受本輪「零失敗／全項完成」結論：規格 V1、V2、V4 的儲存成功訊息仍被背景重讀清掉，獨立瀏覽器測試為 19 passed／3 failed。建議先補正，再部署 5197；本輪未部署、未推送應用程式，未重跑已交付 ETL。

既有 `backend/tests/test_join_replay_worker.py` 修改保留；未修改應用程式 source。此文件為新增驗證交接。

## 環境與驗證

- 本機 Windows 工作樹，前端重新 `npm run build`：PASS（bundle 大小提示不是失敗）。
- 工作流程單元／保存讀回測試：31 passed，0.76 秒。
- 新建暫時 PostgreSQL／API，容器名稱 `codex-ui-review-20261011-*`，資料庫 tmpfs，模型／Hop 派發關閉；不使用 5197／5183 的資料庫、密鑰或資料卷。測試資料僅存於這份暫時資料庫。
- 最新前端預覽 5199，經 proxy 連暫時 API 8765；健康檢查確認 execution_enabled=false 後執行 22 項測試。
- `npx playwright test tests/main-navigation.spec.ts tests/operation-eligibility.spec.ts tests/readiness-response.spec.ts tests/run-detail-failure.spec.ts tests/specification-history.spec.ts tests/ai-profile-drafts.spec.ts tests/tool-load-failure.spec.ts tests/workflow-consistency.spec.ts --reporter=line`：19 passed／3 failed，39.0 秒。
- 此前只有前端、沒有可用隔離 API 的嘗試因前置不足失敗；不將其計為產品缺陷。前置修正後仍失敗的是下列三個規格測試。
- 同一暫時容器執行 `WORKBENCH_ALLOW_DATABASE_TESTS=1 WORKBENCH_VERIFY_DEPENDENCY_LOCK=1 python -m pytest /app/backend/tests -q -p no:cacheprovider --tb=short`：2048 passed／141 skipped／1 warning，45.38 秒。測試使用目前工作樹（包含原有未提交修改），不是 Claude 的雲端環境，不能宣稱數量完全相等或 skip 已驗收。
- 靜態引用掃描：僅 vite-env.d.ts 不在執行 import graph；恢復的 ExecutionReadiness／CollaborationTimeline 均可達。diff --check 通過。

## 必須補正

### 1. 規格保存回饋仍有刷新競爭

`specification-history.spec.ts` 的 V1、V2、V4 均失敗於「已保存待核准規格」斷言，畫面已退出編輯器並重新呈現規格，但成功訊息消失。

`SpecificationHistory.tsx` 的 `useWorkflowRefresh` 仍呼叫 `action(load)`；`action()` 在每次讀取前清空 message，`load()` 同時清空 preview。儲存 POST 發出 workbench:changed 後，背景重讀可能晚於 onSaved 設定成功訊息，造成清除。Claude 雲端的一次通過不能排除這個競爭。

Claude 修正要求：區分背景讀取與使用者操作；背景更新不清空同版的成功訊息與有效編譯預覽。明確切換 Run／規格或開始另一個操作才清除相應回饋。新增可控制 POST 回應及 workflow GET 時序的測試，涵蓋背景更新早於／晚於 onSaved；保留原三個業務斷言，不加固定 sleep 或降低斷言。

### 2. 時間軸仍有舊文案

最新前端 400b95b 搭配 5197 的 GET-only API 檢視已正式交付 Join Run，展開「審查／修訂時間軸與技術詳情」後，仍出現「初步檢查完成，後續流程尚未接通」。來源為 CollaborationTimeline 的 PIPELINE_NOT_READY 映射。

Claude 修正要求：顯示「當時初步需求檢查完成，等待後續審查」等事件事實；原始事件代碼保留於技術詳情，不由舊代碼推論目前服務未接通。補已交付／未交付時間軸測試。

### 3. SA 前置條件與規格 API 不一致

獨立暫時 PostgreSQL／FastAPI fixture 中，model invocation=0，已確認輸入且 deterministic gate CHECKED，直接 POST specifications 回 HTTP 200、SAVED_NOT_EXECUTABLE、version=1。沒有呼叫模型或啟動 Hop。

同一 fixture 設 write_started=true 後再送出，回 HTTP 200、status=INVALID、SPEC_INPUT_NOT_APPROVED。這是語意拒絕，不能把 HTTP 200 當成保存成功。故既有寫入後保護存在，但 SA 前置規則並未由此 API 強制。

後續修正要求：規格保存／核准需要有效、同版 SA 人工核准；預覽 API 可繼續唯讀。驗證必須在同一交易中重新核對，避免套用工作區投影或僅依前端資格。測試涵蓋缺 SA、SA 失效、不同 Run、有效 SA、已寫入／已交付以及重複保存。JSON 的路由覆寫測試只能標為來源契約子系統驗證，不能當成七階段案例。

此後端規則修正會改變既有直接保存路徑；本輪未修改，應另作可審查提交並重跑相依測試，不直接部署為已驗收。

## 已交付回歸

最新前端以本機 5200 GET-only 代理使用目前 5197 API，並非第二輪後端已部署驗收。管理導覽亦以只讀 API 測試通過。

| Task | ZIP bytes | SHA-256 與保存值 | WRITE_STARTED |
|---|---:|---|---:|
| TASK-20261010-0017 | 10417 | 相符 | 1 |
| TASK-20261010-0018 | 11152 | 相符 | 1 |
| TASK-20261010-0019 | 10585 | 相符 | 1 |

此三案回歸沒有非 GET 請求。未修改固定答案、核准、Release 或舊目標。時間軸畫面證據位於忽略 Git 的 `runtime-temp/codex-round2-review/expanded-delivered-design.png`。

## 交接與下一步

1. Claude 修正保存訊息／預覽競爭及時間軸文案，保留原斷言並補時序測試。
2. 後端 SA 前置規則另作提交，隔離測試所有相依核准路徑，不以合成前端放行替代。
3. Codex 重驗上述三項後，再對新的部署版本執行三案與舊 Release GET-only 回歸；現有 5197 仍為前輪版本。
4. 部署與應用程式 GitHub 推送尚未執行。WS-0007 維持 active／部分驗收，不以已交付頁面通過推論其他來源或維運完成。

驗證結束後，已停止前端預覽／GET-only 代理，移除本輪建立的兩個暫時容器與兩個測試網路；tmpfs 測試資料不保留。既有服務與資料卷未移除。私人失敗 trace／截圖保存在 `runtime-temp/codex-round2-review/`。

WS-0007 的 tasks.yml、CURRENT.md 與既有交接已同步 knowledge-workspace，最後提交 `5bac23b24d3a6b146b3407ea057082cff50c42e2`，三份文件均讀回相符。應用程式 repository 未提交或推送本輪新增文件。
