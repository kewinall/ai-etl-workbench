# v2 後續開發與驗證

狀態：進行中，第一段部分完成。起點1c3d069。未部署5197／5183，未呼叫模型、Hop、Vertica或Release。

## 已完成與證據

- Task層級POST run／rerun／supplement統一HTTP410 LEGACY_EXECUTION_RETIRED，移除舊API內模型及Hop執行鏈與無引用imports。歷史GET及下載保留。
- PUT Task在repository交易內取得Task row lock，檢查task_run存在；已有版本回409 TASK_VERSIONED_EDIT_REQUIRED，不改寫原需求、來源、目標或事件。與RunQueue建立版本共用同一Task鎖。
- 新增六項HTTP路由測試：派發開關true／false皆410，repository任何存取立即失敗，證明先拒絕後端副作用；一項隔離PostgreSQL版本編輯拒絕測試，完整Task含logs前後相同。
- 首次全套2064pass／139skip／1fail：新增測試誤用不存在的queue.create，改成實際enqueue後重跑2065pass／139skip／0fail／1 dependency warning，50.91秒。
- 隔離Compose project ai-etl-retirement-20261011，PostgreSQL17、internal network、獨立volume，59 migrations；所有外部派發关闭，使用既有regression映像與本機backend唯讀掛載。未宣稱映像重建或真實ETL驗收。
- diff --check通過。既有test_join_replay_worker.py未修改或提交，SHA256 cc1f19bd4e2da5bf311ed3d3f89802f65e497d5fa40e7cc954d32b6a553e9777。

## 第一段尚待完成

逐寫入API核對與直接拒絕驗證；新增靜態inventory JSON作為清單，各項一律PENDING，不能將現有全套測試外推為全部守門通過。
舊requirements/revise已有版本檢查，但仍需審查競態與無版本Task的reset副作用。Hop準備失敗的受控修正版入口尚待補齊。

## 第二、三段

修正空白舊版區與預建舊節點、過時操作指南、未套用設定儲存入口；更新specification-live及skip清單；新版異常分支和新CSV／Excel／Join完整鏈驗收。保留既有Release，不重設或重跑。

## 下一步

依v2-write-api-inventory-2026-10-11.json逐項讀取handler與service，補有效／缺少／失效／跨Run／已交付／重複請求的適用拒絕測試。完成第一段後才進第二段；5197部署仍需沿用有效部署授權。

## 後續守門核查（第二批，仍屬第一段）

- 命名契約保存同樣取得Task鎖，最新Run已write_started即拒絕NAMING_EXECUTED_VERSION_READ_ONLY，避免已執行版本的命名被改寫而使交付綁定失效。新修正版有全新未寫入Run時不受此限制；不以任何歷史Run曾寫入封鎖整個Task。
- requirement_revision資格及前端表單依實際後端規則限REQUIREMENT_GATE；Hop準備／執行階段不能因gate_result存在就誤顯示可補正。原有失敗結案與QA修正版分支保留。
- 9個寫入入口×3情境直接HTTP拒絕測試27passed：unreviewed、write_started但缺少後續條件、cross-Task；全部通過請求schema後才拒絕，Task、Run完整讀回及所有platform資料表計數不變。新增命名守門與三階段資格測試；相關合併69passed。
- 第二批全套後端2096passed／139skipped／0failed／1 dependency warning，53.17秒；frontend build PASS，僅bundle大小提示。
- Stage-guidance瀏覽器30個合成案例PASS（含新增準備失敗無錯誤補正入口）；原live案例首次因沒有隔離API失敗，專用API僅internal network時無host port mapping，接上獨立browser-only網路後readiness=ready且execution_enabled=false，live獨立重驗1passed（3.4秒）。不掩蓋兩次環境失敗，不宣稱一次31passed或全套瀏覽器通過。
- 私有測試API ai-etl-retirement-20261011-api綁127.0.0.1:8765，Vite5199；與原5197／5183分開。專用API外部派發全false，沒有模型／Hop Worker。該live只建立合成Task並确认輸入，未呼叫模型或ETL。

## 第一段剩餘

inventory九項只是部分情境通過；有效／失效完整binding、正式交付fixture及合法重複請求尚待補齊。其他入口仍PENDING；不可将2096單元整合測試視為逐API全面驗收。準備失敗已明示不可補正，未新增網站重跑流程。第二／三段尚未開始。

## 第三批：舊寫入退場與正式交付守門

- 沒有現行caller的Task requirements/validate、requirements/revise、sample-source/rebuild也統一410；原Run修訂、Naming及Project範例表API保留。移除已無引用的reset_task、RequirementSupplement、sa_prompt、run_codex_sa、run_copilot_sa及其專用imports。旧Release拒絕文案改為未綁定Run，不再說新版交付未接通。
- 新增run_mutability.require_undelivered：在原Task鎖／同交易中只讀查詢既有release_delivery及candidate，不新增狀態。規格保存／核准、一般SDM候選、QA連結SDM及正式候選包建立均在寫入／產生檔案前驗證；歷史GET／下載保留。
- 新增5項隔離PostgreSQL交付guard測試：先建立有效規格與SDM，再於同一回滾交易內保存明示合成的delivery／portability紀錄。各入口重複兩次皆409，Task Run讀回、所有platform資料表計數及產物檔案清單不變。這證明terminal-record守門，不是模型／QA／ZIP全鏈驗收；不繞過immutable trigger或刪除歷史，finally rollback整份fixture。
- 初次小測試因前輪live留下approved queued Run而拒絕2個fixture（14passed／2errors）；沒有修改前置檢查或重跑該案例，改用獨立ai-etl-followup-backend-20261011資料庫，與瀏覽器驗收DB分開。
- 完整回歸第一次2105passed／2failed／139skip：兩個舊Mock把新增查詢當成已交付。fixture改成明確existing Run＋no delivery，保留原QA及checksum拒絕業務斷言，沒有放寬產品守門。
- 最終全套2107passed／139skipped／0failed／1 dependency warning，54.86秒。相關5項交付、SDM、SA及舊入口合併25passed。Diff check PASS。原Join未提交修改SHA256不變。
- 第一段仍partial，inventory其餘操作需要按適用情況補逐項覆蓋；有效／失效SA規格、Hop單次派發與SDM idempotency既有測試本輪全套通過，不把合成terminal-row測試視為真實交付案例。第二／三段尚未開始。
