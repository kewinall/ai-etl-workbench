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

## 第一段工程驗證收斂

- 完成交付前置檢查延伸：版本建立／修訂、輸入核准／取消、SA／Developer／QA預約、SA／QA核准、Oracle保存／核准、Hop派發、只讀比對恢復及執行／準備結案。均使用原Task鎖及既有release_delivery記錄，只限制寫入，不變更歷史GET。命名保存也直接確認Task交付記錄。
- 已交付fixture擴為21項（5個HTTP artifact操作、16個直接transactional service操作）；各重複兩次明確拒絕、Run及所有platform計數與artifact file list不變。沒有模型或引擎實際呼叫，合成terminal記錄不代表真實QA／ZIP驗收。
- 相關核准綁定／單次派發／Oracle／交付21項合併54passed；完整最終2123passed／139skip／0failed／1 warning（60.04秒）。新guard仍保留尚未交付時的有效核准、失效拒絕及原idempotency業務斷言。
- inventory逐項標明Task/Run寫入、純預覽POST、停用入口及非工作流API；不是整個平台全部API安全稽核。正式Release approve對已交付僅允許同binding/checksum的既有交付acknowledgement，不產生新檔／事件／派發，不能當成重新核准。
- 第一段工程里程碑可階段性通過，進入第二段。真實provider與完整執行證據仍在第三段，WS-0007保持active。準備失敗修訂資格與後端一致，未提供不合資格的直接重試。


## 第二段：介面精簡與舊資料邊界

- 新Task不再insert八個停用Task流程的PENDING節點；保留建立事件、request-key重複建立保護、既有task_node_run資料與GET。隔離PG測試確認八次並行建立唯一ID、新Task nodes=[]、舊節點讀回完全不變。
- LegacyTaskRecords自動讀取history-assets、依Task id綁定回應。只有實際非PENDING節點／錯誤／歷史執行狀態／產物才顯示舊區；普通建立及命名INFO紀錄不觸發空白區。失敗可重試GET；不增加写入或執行。沒有資料的SQL／Hop Log標題也不顯示。
- 未接入執行流程的validation_release_policy在設定頁改唯讀保存值，隱藏Save、分類取消及差異套用；原保存資料與後端policy限制保留。設定草稿測試移用實際AI預設，保留X-Settings-Version、跨分類草稿、送出鎖定、失敗保留及離開攔截業務斷言；policy API限制仍實测。
- 操作指南及尚無Run說明改為當時檢查紀錄／目前七階段，不再宣稱後續流程未接通或指向舊頁籤。
- 新增3項瀏覽器案例：空白舊節點／管理log不顯示、真實形狀的舊失敗節點可展開、history-assets讀取失敗恢復只做GET。保留舊ZIP/XML下载位元組檢查、全部八個歷史節點詳情與返回路径。
- focused36PASS；第一輪完整瀏覽器98PASS/39skip/3FAIL，其中2個過期手動刷新／空白歷史fixture，1個並行runner共用test-results產生ENOENT。改為明確保存歷史fixture、自動GET，並分離輸出目錄後再完整重跑，不將runner錯誤當成產品完成證据。
- 後端最終2124PASS/139skip/0FAIL（64.52秒），frontend buildPASS。静態reachability84個有效檔案，unreachable只有vite-env.d.ts型別宣告，無動態import。
- 隔離API8765重新啟動以讀取最新mounted source，前端5199使用該API；5197／5183未部署或更動。未執行真實模型、Hop、Vertica、QA或Release；既有Join未提交修改hash不變。

- 第二輪完整瀏覽器最終101PASS/39skip/0FAIL（2.7分鐘），獨立輸出runtime-temp/v2-followup-stage2-browser。第二段工程驗證可阶段性收斂，第三段仍未完成；skip不是PASS或真實全鏈驗收。


## 第三段第一批：opt-in規格流程與標準答案草稿

- specification-live改走共用版本／目前設計、執行確認、交付階段及收合時間軸；保留規格常數、核准、SDM指紋、候選下載、編譯checksum、答案版本／精度、失敗保留、事件計數與390px斷言。SDM歷史檢查搬到交付頁；不覆寫workflow資格。
- 使用既有syntheticSaApproval fixture建立同Run有效SA人工核准，CONTROL一次執行限定新測試Project，其他待核准／排隊Run不消費。API部署false且全部model/Hop派發關閉；這不是模型驗收。
- 首次失敗證明輕量隔離API未配置WORKBENCH_ARTIFACT_ROOT。只重新建立ai-etl-retirement-20261011-api，增加獨立named artifact volume並保留原停止容器；讀取原env於記憶體，不輸出值，未動5197/5183。fixture新增前置assert，避免晚到文件步驟才失敗。
- 實跑發現OracleHistory依saveOp.enabled決定是否mount答案表單；failed POST也觸發唯讀刷新，loading短暫資格false導致表單unmount，清空已填資料。保留同Run/spec已啟用editor key，資格不明時仍停用表單，版本切換不沿用草稿。新增mock回歸確認503和共用GET刷新仍保留123，只有一次POST。
- 新規格live最終PASS14.2秒，Task TASK-20261011-0067 / Run d3884cd0-2d98-4eaf-a8b2-02e5449db763 / specification3056e573-7700-4e85-a100-74727c5f11bf。artifact為候選SDM XLSX，非QA／正式Release；未寫Vertica，write_started=false。finally取消該合成Run並還原測試改寫設定。
- 新增v2-opt-in-inventory-2026-10-11.json：靜態條件與environment keys、未實測界線；93個有conditional gate的測試檔不是93個skip instance。預設backend139／browser39 skipped仍需按證據類型分段實測。另標示Copilot/upload/QA-Hopf授權/復原歷史中的舊selector，未宣稱全數補正。
- 第三段仍partial：新的CSV／Excel／Join真實七階段、其他opt-in舊入口與原正式Release只讀回歸未在本批執行。5197維持原source，app commits只在本機，未推送。

- 第三段第一批最終預設瀏覽器102PASS/39skip/0FAIL（2.8分鐘）；新增草稿測試回放dfa6a00旧OracleHistory必FAIL（清空成0筆），修正後PASS。新增artifact-root前置後規格live再PASS15.6秒，TASK-20261011-0096 / Run143b9570-6988-4f82-82ea-99b9ebaf7e30，全部合成case finally取消且設定還原。Build PASS。

## 第三段第二批：CSV 換檔與既有正式案例唯讀回歸

- upload-live 移用可見且唯一的 Task 表單、七階段頁面、共用狀態刷新與修訂差異確認；CONTROL helper 先驗證 execution_enabled=false，再只消費測試 Project 唯一排隊 Run，沒有消費其他案例。
- 實跑揭露 CSV 建立資料帶入 null 的 excel_selection_v1 / json_profile_binding_v1，換檔 whitelist 誤拒絕。前端只去除這兩項 null，後端兼容已保存 null；非 null 外來契約與未知 metadata 仍拒絕，沒有放寬任意來源支援。新增六項拒絕測試及兩層 null 整合 fixture；相關 12 passed。
- 專用隔離 API 增加 runtime-temp 上傳 named volume，原 source mount 仍唯讀；只重新建立該測試 API，保留停止容器及原 artifact volume。未動 5197/5183。
- 最終 upload-live 1 passed（9.7 秒）：TASK-20261011-0100；需求修正版 06b39a5f-3736-4f85-8430-74e8cf3064ef；換檔版 baad490d-b7e0-4866-b505-47b077d450a2。舊檔、輸入及核准保持，換檔版未沿用核准；write_started=false。finally 取消自己 Run、還原設定。證據 runtime-temp/v2-followup-upload-live-final。
- 先前失敗包括舊 hidden form locator、舊修訂提交路徑及上述真正的 CSV metadata 422；修正後保留原業務斷言重新實跑，不能將初次失敗記為通過。
- 建立來源文案與現有能力一致：CSV、Excel、雙 CSV Join 有受控真實案例；JSON／資料表與其他來源仍明示未完整驗收，Task 建立不代表該版本有執行資格。
- 修復 native-acceptance-delivery 的舊狀態文字與下載入口，完整保留七階段、版本、390/768/1440px、鍵盤、SDM 歷史下載及 ZIP byte/SHA 斷言。使用目前前端 source（Vite 5200）連至原 5197 API；不是部署目前後端。
- 正式三案唯讀最終 10 passed（42 秒）：9 個案例／寬度組合加 opt-in proof。路由攔截非 GET/HEAD/OPTIONS，before/after Run 與 Release 完整讀回相同，每案 WRITE_STARTED 仍為 1，ZIP 指紋與保存紀錄相同；零瀏覽器寫入。證據 runtime-temp/v2-followup-native-readonly-final。這是既有真實案例回歸，不能替代本輪新三案七階段執行驗收。
- 本批完整後端 2132 passed / 139 skipped / 0 failed（60.99 秒），frontend build PASS；完整預設瀏覽器 102 passed / 39 skipped / 0 failed（2.9 分鐘），輸出 runtime-temp/v2-followup-upload-default-browser。skip 仍不算 PASS。
- 尚待：Developer／QA-Hop／Copilot／失敗歷史等 opt-in 舊入口逐項修訂、適用異常分支與新的三案真實七階段。5197 API/web 未部署本批，5183 未變，沒有模型／Hop／Vertica 寫入／QA／正式交付建立。原 Join 未提交修改保持原 SHA256。

## 第三段第三批：授權操作測試常態化

- Developer 與 QA-Hop 兩項原本是合成 API 測試，卻要求既有真實導航環境才執行，預設一直 skip。新增獨立 authorizationWorkspace fixture，所有 API 讀取合成、未預期寫入直接攔截，沒有真實 provider 或資料庫副作用；資格只是前端測試輸入，不代表後端通過。
- 改走設計／品質／執行確認與共用刷新，保留原確認 checkbox、授權內容 binding、單次 POST、保存讀回、409、DDL、queued 隱藏授權及 390px 斷言。移除兩項不必要 opt-in，未移除真正 provider 測試的授權要求。
- 首次實跑 1 passed / 1 failed：Developer 409 訊息被 changed 事件引發的背景 GET 清除，重新顯示授權。修正背景 GET 保留錯誤，錯誤存在時不显示新授權；明確「重試讀取 Developer 狀態」讀回後才清除錯誤。新測試確認共用刷新仍保留衝突、checkbox 不出現、POST 仍只有成功與衝突兩次；明確 GET 恢復不送模型請求。
- 最終 focused 2 passed（3.2 秒），build PASS（原 bundle-size warning）。Developer 保存文案改為檢視下方規格，資料未更新使用共用刷新，不再要求已移除的局部刷新入口。
- 本批不變更後端，後端有效結果沿用第二批 2132 passed / 139 skipped；完整預設瀏覽器最終 104 passed / 37 skipped / 0 failed（2.8 分鐘），證據 runtime-temp/v2-followup-authorization-default-browser。減少的兩項 skip 是現在每輪必跑的合成授權測試，並非真實 provider 驗收。Copilot 真實模型與 recovery-history 真實失敗歷史舊入口仍待修訂／實測；新三案完整執行未完成。

## 第三段第四批：真實失敗歷史與重複畫面

- recovery-history-readonly 改用共用版本、結果／需求階段、完成輸入收合區及瀏覽器返回，保留 COLUMN_NOT_FOUND、行號、日誌指紋、0 筆結案、parent_run_id、三種寬度與零寫入斷言；before/after 父及子 Run 完整相等，每個 WRITE_STARTED 仍為 1。
- 原 5183 沒有 workflow-status API；5197 固定證據代理僅允許原已驗收 CSV／Excel，不擴大其 production allowlist。另啟動僅本機 8766 的臨時 GET-only harness，固定 TASK-20260927-0076，使用目前 summarize() 彙整原始 5183 GET 證據；不接資料庫、不提供任何寫入 route、不保存合成 Run、不部署 5183。現在前端 Vite 5201 讀取該 harness，不等於 5197 部署驗收。
- 真實父 Run a91856ca-bc20-4af1-8e18-fb038b12c4bc；修正子 Run d8fe2f6f-8305-4d58-88ee-affb1a85a547。原父明確 HOP_EXECUTION_FAILED/CLOSED_WITHOUT_RETRY，子保留 HOP_EXECUTED_QA_REQUIRED 與正式交付紀錄。首次測試揭露結果頁在 RunArtifacts 與 StageWorkspace 各顯示一次診斷；移除 StageWorkspace 重複實例，保留 RunArtifacts 原診斷及結果結案元件。
- 第二次因完成階段 lazy details 尚未讀回就檢查 count 失敗；測試改等真實可见 summary 再展開，沒有固定延遲或放寬業務斷言。最終唯讀 1 passed 5.9 秒；加完整父子不變與兩次寫入數量確認後再 1 passed 7.8 秒。原證據未修改，沒有發送模型、ETL 或結案 POST。證據 runtime-temp/v2-followup-recovery-readonly/browser-immutable。
- failed-revision 原為 mock 測試但被既有導航環境 skip 隱藏，且仍走過期需求頁診斷／直接提交。改独立合成 fixture，真正結果頁只一份診斷、上方明確修正版入口、預覽差異與確認、新目標、原 checksum、父資料保留及子核准清空；1 passed 2.5 秒。此項現在預設必跑，不代表真實故障再執行。
- Copilot standalone 測試更新需求審查與共用刷新；啟動前要求 execution_enabled=false、明確隔離容器與 CONTROL 相同、明確已連線檢查的模型，拒絕 5183／5197 容器；不再使用預設生產容器或硬編碼模型。CONTROL 只消費新測試 Project 唯一 Run。測試語法與探索確認，尚未執行真實模型，不在三新案例之外新增實際模型用量。
- 本批 source build PASS；完整預設瀏覽器最終 105 passed / 36 skipped / 0 failed（2.9 分鐘），runtime-temp/v2-followup-recovery-default-browser；新增必跑失敗修訂為合成 API 工程檢查，skip 減少不代表多一次真實執行。後端未變更，2132 passed / 139 skipped 沿用前批。三新真實案例仍待 5197 受控部署與逐階段完整驗收；WS-0007 不標完成。

## 5197 受控部署與既有正式案例回歸

- 工程 source a7a666f 依既有 5197 驗收範圍部署；先保存五個既有正式 Release（5197 三案＋5183 固定唯讀 CSV/Excel）的 ZIP SHA、位元組、完整 Run 雜湊、更新時間及 WRITE_STARTED=1 基準。
- 使用既有 stage-guidance + ui-acceptance compose，UI_ACCEPT_PROJECT_ID 固定原隔離驗收專案，只 up --no-deps --build api web。沒有 migrate、重啟控制 Worker、變更資料庫/volume、部署 5183 或重跑 ETL；Compose 成功 exit 0，API healthy。
- 前端實際 index-BppNKZAm.js，全部 deployed backend/app Python source 正規化 LF 指紋與本機相同。八個受保護容器 ID/image/StartedAt 完全相等：5197 PostgreSQL/control/evidence/portable DB，5183 api/web/PostgreSQL/control。
- 部署後五個原 Release checksum、bytes、Run hash、updated_at 及 WRITE_STARTED 完全不變。真正部署的 5197 三案七階段、三種寬度、键盤、下載及 SDM 歷史 GET-only 回歸最終 10 passed（24.6 秒），非 GET 攔截且無寫入。證據 docs/verification/v2-followup-5197-deploy-readback-2026-10-11.json，私有 runtime-temp/v2-followup-5197-deploy。
- 5197 現在 source a7a666f；此部署回歸僅為既有資料只讀驗證，新的 CSV／Excel／Join 完整執行仍未完成，不能用此回歸替代。下一步以新 Task、新 ui_accept_* 目標及執行前固定答案，經正常網站建立與原核准，逐階段保存新模型、Hop、QA、可攜及 ZIP 證據。

## 新三案七階段真實驗收（2026-10-11）

- 以使用者既有「授權三案例全部自動核准、執行與交付」及本輪開發驗證範圍，正常網站建立三個新 Task；網站是所有需求修訂／核准／模型／Hop／交付意圖的入口，沒有直接寫控制資料庫或覆寫工作流資格。固定 `examples/ui-acceptance/expected.json` SHA-256 `c31a5140551ccdab58185fc64609fab77e677a7cae9f4ab587a688340db5b05a`，執行前保存並核准；沒有從結果反推答案。該固定檔的歷史 `full_chain_accepted=false` 不改寫，新的驗收結果分開保存。

| 案例 | 新 Task／最终 Run | 全新原目標 | 固定／實際 | 節點 | 原写入 |
|---|---|---|---|---|---|
| CSV | TASK-20261011-0001 / f65777ad-8457-49c5-8cb0-8cd0bf0ab84b | ai_sample.ui_accept_csv_20261011_v2 | 2 / 2 MATCH | 7 完整 | 1 |
| Excel | TASK-20261011-0002 / 0db71099-170f-497d-a35f-c2bbb927994b | ai_sample.ui_accept_excel_20261011_v2 | 2 / 2 MATCH | 7 完整 | 1 |
| LEFT JOIN | TASK-20261011-0003 / 2980c558-ee7b-426a-a57a-fc40d5a18e34 | ai_sample.ui_accept_join_20261011_v2 | 5 / 5 MATCH | 9 完整 | 1 |

- 初步檢查實際走 NEEDS_INPUT → 網站差異預覽 → 新版 → 重新輸入確認；三案都有原版本保存，沒有修改舊 Run。CSV 真實 SA 第一次要求補明聚合目標型別及新表 DDL，保留 NEEDS_INPUT invocation `3a66d148-c65b-4242-a69b-24e9d5406670`；另建新版明定型別／新建表／不 DROP、不 TRUNCATE，再另行授權 SA。修正版 SA READY_FOR_REVIEW，沒有沿用旧 SA 核准。
- 三案当前 SA／Developer／QA 均为真实 LOCAL_COPILOT `copilot/gpt-5.4`，每次 cli_sessions=1、automatic_retries=0、tool_execution_count=0；QA 均 PASS 並另存人工核准。加上 CSV 退回共 4 次 SA、3 次 Developer、3 次 QA。token 用量不能完整取得，保留 null／PARTIAL，不宣稱精確 token 統計。
- SELECT-only 原目標預檢證明三個表均不存在；只更新 acceptance-hop/replay 共用 Worker image至当前 source，未重啟既有服務。現有 intent consumer 只消費網站已授權預約，每個子 Worker 明確 task-id/run-id，marker 原子預約不重試；本輪不新增 approval bypass。Hop 2.12.0 原執行全数完成，逐節點原始 Log checksum 和 WRITE_STARTED=1 核對；再透過獨立 Vertica 連線 SELECT 比對固定 multiset（小數／NULL 保留）。
- 三案依序完成 QA、SDM、候選 ZIP，隔離 UiAcceptPortable 執行原 HWF/HPL/DDL並 PASS。另以 SELECT 核對隔離结果 2／2／5 與候選 receipt checksum；连接與原目標不同，不重跑或清理原目標。
- 網站保存正式 Release 后實際下載 ZIP，ZIP 位元組／SHA、manifest 綁定及五個產物 hash／size 均一致；SDM 可開啟且有工作表，全部七階段完成。正式交付來源與下载證據：`v2-followup-delivery-2026-10-11.json`；原執行／獨立結果：`v2-followup-native-readback-2026-10-11.json`；隔離可攜：`v2-followup-portability-2026-10-11.json`。
- 實際部署5197新三案七階段390／768／1440px、鍵盤、正式ZIP下載、SDM歷史、Run重载回歸 **10 PASS（25.0秒）**。每個画面維持已正式交付及同Run，無水平溢位／pageerror；測試攔截非GET且Run/Release before-after完全相等。這一輪窄版驗證是完成後的七階段查閱及下載，不宣稱窄版重新操作全部真實寫入。正常寫入驗收使用1440px；表單窄版与異常分支另有工程測試。
- 五個既有正式 Release 再次 GET-only 回歸 PASS，指紋、bytes、Run hash、updated_at與WRITE_STARTED仍等於部署前基準。5183没有部署、既有已交付目標沒有重跑。原 `test_join_replay_worker.py` 未提交内容SHA仍為 `cc1f19bd4e2da5bf311ed3d3f89802f65e497d5fa40e7cc954d32b6a553e9777`。
- 驗收脚本早期失败如實保留在私有 `runtime-temp/v2-followup-live-state.json`：native fetch ok 型別、Excel exact label、Task/context切換及等待 naming/developer API路径。兩次等待超時時寫入已成功，先GET確認，沒有重送成功意圖；修正腳本後續從保存狀態接續。兩份額外上傳保留，沒有刪除旧資料。這些不是首次全通过，也沒有將腳本失败冒稱產品通过。
- 本批没有修改 application source，backend2132 PASS/139skip及默认browser105 PASS/36skip沿用前批当前source，不重複冒算。native readonly test新增可選proof路径，新三案真实回归已實跑；其余条件测试並未因三案通过而视为全部完成。

本輪三案正常七階段可階段性驗收；WS-0007整體仍進行中。尚待独立里程碑：已交付版本修正版能力、JSON／資料表完整執行、REPLACE／UPSERT、維運復原、完整列印報告及人工成效基準。QA補證、執行失聯、網路回應遺失等保護有工程或保留歷史證據，未在这三案刻意另作新的真實故障／模型成本案例。下一步依 opt-in inventory 的證據層次選定尚未實測分支，補隔離回歸及清楚交接，不重跑這三個已交付目標。

## 異常分支第一批：背景更新與回應遺失

- `comparison-recovery.spec.ts` 原四項是合成 UI 測試，卻只接受5195且先真實建立Task，停留舊需求頁入口。改用既有 `authorizationWorkspace` 純瀏覽器fixture，所有GET合成、非預期寫入攔截，走現在結果階段；保留MATCH/MISMATCH/FAILED/409、確認binding、單次POST、重新載入、390px及Hop原失敗狀態斷言，新增已受理但POST回應遺失分支。不再需要改真實設定或5195。
- 首次3PASS/2FAIL（22.2秒）：409及回應遺失警示在`workbench:changed`後迅速消失。原因是HopDispatch背景refresh把data設null，卸載ComparisonRecovery，且後者背景GET又清除error；原錯誤與待核對狀態不能保存。
- Hop／QA背景讀取保留原data、error、consent，編輯同意時暫停背景重讀；明確局部GET重試才清除error與重新檢查派發。未確認寫入結果時隱藏新授權表單，不重送POST；ComparisonRecovery也不在背景GET清除error，主工作區只保留共用刷新，局部按鈕仅讀取失敗或送出不明時出現。
- QA回應遺失四分支首次4PASS/1FAIL（15.0秒）：QA未保存時背景GET仍顯示授權checkbox。補上error守門；正常單次QA/Hop授權、已受理／未受理回應遺失、明確GET核對、reload及單次POST全部通過。
- 新增QA／Hop服務未就緒原因與禁用操作、QA NEEDS_REVIEW補證複核只帶前次invocation另預約新審查、無Hop操作。後者是合成API互動驗證，不宣稱新真實QA複核完成；原三案已交付只讀。
- 最終focused **14PASS（24.0秒）**，build PASS（原bundle-size warning保留）。全部使用当前source5199＋純合成瀏覽器API，未呼叫模型、Hop、Vertica或交付；5197尚未部署本批，5183未更動。原Join未提交hash不變。backend沒有修改，2132PASS/139skip沿用前批。
- 完整預設瀏覽器最終 **117PASS／32skip／0FAIL（3.4分鐘）**，證據 `runtime-temp/v2-followup-abnormal-default-browser`；減少4個skip是比對恢復合成測試常態化，新增8項合成分支，不等同新真實故障驗收。執行失聯／準備核對的合成測試仍依賴舊有導航環境，下一批繼續常態化並保留原確認/結案/禁止重跑斷言；真實故障案例仍需獨立隔離DB，不在已交付Task注入故障。

## 異常分支第二批：失聯結案與 QA 核准

- 執行結案、準備失聯核對、QA核准及QA歷史四份合成測試移除舊Task導航與5183參考來源，全部改用 `authorizationWorkspace` 在現行結果／品質階段；所有API攔截，不讀寫production或以合成資格冒稱後端有效核准。
- 執行结案成功／409／已保存但POST回應遺失：原1筆輸入保留、確認後雙擊仍只1次POST、明確GET確認才恢復；準備核對保留目標不存在(null)與存在零筆(0)區分、一次確認、不需證據檔案、reload以及禁止重跑原断言。這5個原功能分支實跑通過，不修改原結案邏輯。
- QA核准成功／409／已保存但回應遺失第一次共8項為6PASS2FAIL（26.0秒）；兩個失敗重現QAApproval在背景useEffect清掉error、重新開放核准。取消背景清error，錯誤時隱藏核准表單，只有明確GET重讀才清除警示；同意勾選中不被背景更新重設。修正後8PASS（16.8秒），一次POST、原binding、reload、390px與非預期寫入攔截均保留。
- QA歷史未知模型結果、讀取503、失效建議与390px顯示轉用共用更新，讀取失敗才提供局部重試；原摘要、token未提供、不自动重送、旧資料清除與上游異動斷言保留，1PASS（2.0秒）。这些是合成互動證據，不宣稱真實故障或新模型審查。
- Build PASS（原bundle-size warning保留）；backend沒有變更，2132PASS/139skip沿用。本批完整瀏覽器 **126PASS／27skip／0FAIL（3.6分鐘）**，五個原合成skip改為必跑并新增四個合成分支；不冒稱真實故障處理完成。5197 web-only受控部署驗證完成後補記；部署前先保存八個新舊正式Release與九個保護容器metadata，GET指紋檢查已通過。原未提交Join SHA不變，不納入提交。
