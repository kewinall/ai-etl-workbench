# 順序 1、2 驗收（2026-09-17）

## 範圍與結論

本次完成先前指定的順序 1（解除 Release 內容篩檢失敗）及順序 2（設定／版本／重複請求／中斷恢復及人工核對必要入口）。不代表整體 P0–P3 完成，不包含真實 SA／Developer／QA 模型鏈、正式 Release 核准／下載或可攜執行驗收。

## 驗收對照

| 要求 | 證據 | 判定 |
|---|---|---|
| 定位封裝誤判，不更改機密或跳過短值 | 真實保管庫值命中標準 OOXML 屬性名稱，解析後文字／屬性值未命中；改為明確標準結構白名單，值及未知名稱仍檢查 | 通過 |
| 正常候選可封裝，含敏感內容仍拒絕 | 定向篩檢 20 passed；包含屬性值、儲存格、註解、PI、實體、拆分文字、未知名稱及 DTD 拒絕；真實 PG／保管庫／合成 QA／SDM 封裝 6 passed | 通過；候選不是 Release |
| Task → Project → 平台設定、無有效設定停止、不沿用本機預設 | 隔離 PG 全套 740 passed／23 skipped，含 test_execution_settings、test_run_queue_integration、execution authorization/reservation 等；真實 Hop Run 的 AI／連線 origins 均為 PROJECT，執行用固定快照與指定版本 vault 機密 | 通過；模型本身本次未呼叫 |
| 重複请求及並行領取不造成重複工作 | PG idempotency、parallel_workers_claim_only_once、only_one_worker_can_consume_execution_consent；真實中斷 Run 相同 request key 返回同 Run，舊授權再領取回 EXECUTION_AUTHORIZATION_CONSUMED | 通過 |
| 中斷與服務重啟不遺失狀態、不自動重寫 | 真實 Hop 寫入後、結果尚未回報時 kill 唯一測試 Worker；重啟 PostgreSQL／API／CONTROL，租約自然到期轉 HOP_RESULT_UNKNOWN；目標結果、寫入事件及保留紀錄均未增加 | 通過 |
| 人工核對能保存，不偽裝成功／觸發重跑 | 真實瀏覽器 → API → PG 保存、重載、重送同回應、異動 payload 回 409；不可變資料表；原 outcome／write_started／私有 log／授權保留；最終 FAILED 表示停止此次嘗試，不表示 DB 已 rollback | 通過 |
| 必要網站操作與設定保存正常 | 瀏覽器專案 CRUD、歷史節點／返回、設定保存重載、設定變更使舊確認失效等 4 passed（16.1 秒）；核對表單 mock＋舊六頁籤 2 passed；真實中斷核對 1 passed（4.7 秒） | 通過指定範圍；非全站無缺陷保證 |

## 真實中斷案例

- Project：`70678ea0-4a84-4d69-ae68-b98b4928f4e1`
- Task：`native-pilot-73bb4b6014b64006aba78ef02aed70a1`
- Run：`1b228586-f647-42ec-8572-ba12b1338d6c`
- Schema／table：`ai_sample.pilot_73bb4b6014b64006aba78ef02aed70a1`；本次新建、登錄並綁定 Run，未 drop 或覆寫其他表。
- Hop log checksum：`f7d8b6aa2eabe15baec103804b35b55dd65f0fae6175fe89210a4f0aff03735a`
- 中斷點：真實 Hop 已回傳完成、私有 Log 已保存，測試 wrapper 在交還結果給 execute_once 前等待。這不是把 DB 狀態直接改成未知，也不是模擬引擎；不宣稱測試了 Java 在 COPY 途中被殺死的每一種情況。
- 中斷前：RUNNING、write_started=true、租約存在；Vertica 一列 `A / 301.35 / 2`；WRITE_STARTED=1、reservation=1。
- 測試 Worker `ai-etl-crash-probe-20260917b` 強制中止後 exit 137。未重新啟動此 Worker。
- PG／API／CONTROL 重啟後，自然租約到期：NEEDS_REVIEW、HOP_RESULT_UNKNOWN、租約清除；一列結果及計數不變。
- 獨立唯讀查詢證據：[crash-inspection-2026-09-17.json](crash-inspection-2026-09-17.json)。此檔案 SHA-256 為 `a425cd612086393051d59f2ae8e09e7cfc68d164c29aa09cc774df233c5c33e1`。
- 瀏覽器使用此證據完成核對；檔案只在瀏覽器計算 SHA-256，不上傳原文。
- 保存 reconciliation：`0027ee16-594d-495b-8faa-d25fa11a6d55`；核對目標筆數 1；CLOSED_WITHOUT_RETRY；原 outcome 保留，狀態 FAILED、write_started=true。
- 結案後獨立再查 Vertica，仍為同一列。WRITE_STARTED=1、reservation=1、reconciliation=1。
- 回滾負向驗證：舊授權再次領取回 `EXECUTION_AUTHORIZATION_CONSUMED`；延遲成功回報回 `LEASE_LOST_OR_HOP_NOT_STARTED`；未新增寫入或核准。

## 測試與部署

- 本機完整後端：667 passed／96 skipped（7.15 秒）。
- 新獨立 PostgreSQL 環境：全部 44 migrations 初始化成功；740 passed／23 skipped（17.78 秒）。使用 `deploy/compose.p0-tests.yml`，獨立網路與測試資料卷，無對外連線與 published ports，未接觸 Pilot volumes。測試結束後容器已停止；測試資料卷保留。
- 真實 PG 人工核對 API 回滾測試：2 passed，覆蓋 404、409、確認缺漏、冪等、不可變歷史、拒絕遲來回報、寫入次數不變。
- migration 044、API、網站與 CONTROL 已部署；API ready，PG healthy；ETL／模型自動派發未開啟。
- 已核對本機檔案與部署 API SHA-256 一致：
  - release_content_gate.py：`bac070b353f160fe4871a06a5e3a0d65fa70ea6810eb0d4fdab1f6f2659b4e6b`
  - execution_reconciliation.py：`fa7f4e0cf5ea3378160ec6f282c3d987693d12204eb84b916b8f4a8adc92161b`

## 保留的失敗與限制

- 首次中斷探測使用缺少 JDBC 的舊測試映像，未抵達中斷窗口，不能算成功。Run `122fc28e-47cc-490b-a25e-6eddff763740` 與私有日誌保留；沒有在同一 Run 重試。驗收工具已新增 JDBC 前置檢查，改用含驅動的 Worker 執行上述新案例。
- 原 9 月 13 日成功 Run `7fc2be0d-f1a8-4ea5-a9ed-74107369001b` 未被結案或人工 QA 核准。
- 人工核對是 Operator 的證據聲明；平台保存指紋及觀察筆數，不把它當自動 QA 或資料回復證明。
- 此次不消耗真實模型額度，不發布正式 ZIP、不推送 GitHub。不代表 P1–P3、全站回歸、備份還原／Windows 舊 DB 遷移或所有中斷時序均已驗收。

## 重現方式

- 隔離回歸：`docker compose -f deploy/compose.p0-tests.yml up --abort-on-container-exit --exit-code-from tests`。
- 原生中斷工具：`backend/tests/run_native_vertica_pilot.py`，明確指定 `WORKBENCH_REAL_VERTICA_PILOT=1` 與 `WORKBENCH_CRASH_PROBE=1`；必須使用含 Vertica JDBC 的 Worker，停止 CONTROL 且沒有 QUEUED／RUNNING 工作。工具只建立新 Project／Task／登錄測試表，不重跑舊表。
- 外部監督必須在 `HOP_FINISHED_BEFORE_ACK` 後中止該次唯一測試容器，重啟控制服務並等待自然租約到期，獨立查詢目標，再使用新的真實證據執行 `frontend/tests/execution-reconciliation-live.spec.ts`。不要重用本文件已結案 Run 當成新的正向測試。
