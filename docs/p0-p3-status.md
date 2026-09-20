# P0–P3 當前交付狀態

本文件為工程與網站整合的當前狀態；歷次實作細節保留於 pilot-implementation.md。局部測試通過不等於階段完成。

## 最新：本案例順序 3、4 真實交付驗收通過（2026-09-20）

- 使用者明確同意正式 Release 後，已從網站核准同一 Run，狀態 RELEASE_READY；實際點選下載取得 download event，另以相同下載入口保存本機 ZIP 並核對 SHA-256 `f32b964c8071d37dd854f653320eb4ce41041ae01e92220a026aa27d9bb8da2d`。
- Release `a76bae7f-3b13-4dda-ac3f-68f8b41081de`，10,452 bytes。6 個成員與 manifest 雜湊通過；HPL/HWF/DDL/parameters 與已實際執行候選包完全相同。正式 SDM 兩頁渲染與 QA/來源 SDM/可攜指紋核對通過。
- 核准後唯讀原 Vertica MATCH 3/3、原寫入 1 次、可攜執行 1 次、模型累計 5 次；兩次歷史 NEEDS_REVIEW 保留。沒有新模型或 ETL 呼叫。
- 僅此合成案例的順序 3、4 完成；P0–P3 其餘情境、production TLS 與全平台驗收並非完成。實作原始碼仍為本機未提交工作樹，不能稱為已同步 GitHub。

## 歷史：人工 QA 與隔離可攜驗收通過，待正式交付核准（2026-09-20）

- 同一 Task/Run 已依使用者同意完成網站人工 QA 核准、QA 關聯 SDM、候選 ZIP 保存；全新 Vertica 目的地的 HWF/HPL/DDL 單次真實執行 PASS，EXACT_MULTISET 3/3。原目標唯讀再查仍 3/3、原 WRITE_STARTED 仍 1。
- 新增 opt-in 隔離 Compose、只讀前置檢查；隨機機密僅存 Docker volume，沒有原資料卷或公開埠。既有測試映像無 TLS，本機 internal network Pilot 使用明確 disable，非 production readiness。
- SDM 重複顯示確認為 sibling React key 衝突，最小修正後實際重載及再次取得 SDM 均只有 1 份歷史區塊。今日完整隔離回歸 844 passed、23 skipped、1 warning；前端 build 通過。
- 順序 3 本案例通過；順序 4 仍缺獨立正式 Release 核准、正式 ZIP 下載與正式 SDM 最終驗收。沒有追加模型或重跑原 ETL。追蹤 WS-0006，詳細證據見 [2026-09-20 驗收](verification/p0-step-3-4-live-2026-09-20.md)。P0–P3 全平台並非全部完成。

## 歷史：追加真實 QA PASS，等待人工 QA 核准（2026-09-17 21:40）

- 使用者「請追加」明確授權的 1 次 gpt-5.4 QA 已完成，invocation `635f7527-be16-49eb-adb5-bad734024b8b`；prompt v4、context v3，結果 PASS。1 CLI session、0 自動重試、0 工具操作；4.7389 AI credits、1 Premium request，Token 未提供。累計模型 5 次（SA 1、Developer 1、QA 3），前兩次 NEEDS_REVIEW 未改寫。
- 本次入口只允許同一執行由 context v2 補充為 v3；移除新增 execution_details 後必須完整等於前次 canonical context，且需新的明確授權與精確前次 invocation ID。最多三份 QA；不允许上游改版或自動重送。
- 呼叫後唯讀核對 Vertica 仍 MATCH 3/3、缺少/多出 0；WRITE_STARTED、HOP_EXECUTED_QA_REQUIRED 仍各 1，沒有重跑 Hop。網站可查看 PASS 與兩份歷史 NEEDS_REVIEW，已顯示人工 QA 核准關卡，尚未代替使用者核准。
- 完整隔離回歸 842 passed、23 skipped、1 warning（20.95 秒），新版已部署。WSL 曾中斷使服務正常退出；以本次驗收背景保活恢復，未改動原資料或重播 ETL。
- **順序 3 尚待人工 QA 核准；順序 4 的 SDM、隔離可攜執行、正式 Release 核准與 ZIP 驗收仍未完成。** 下方為歷史記錄，不得將模型 PASS 說成完整交付通過。

## 歷史：順序 3 真實協作已執行，但 QA 尚未通過（2026-09-17 21:20）

- 21:27 接續：未增加模型呼叫或 Vertica 寫入。可攜 Worker 現在除了 Pipeline 節點成功，還要求固定 HWF 的 action start → result=true → workflow finished 三項唯一且順序正確的紀錄；缺失、重複、失敗或其他 Workflow 均不通過。無網路 Hop 2.12 原生成功／缺來源失敗兩案例及 12 個程式負向檢查共 14 passed（Dummy sink，並非正式候選 ZIP／Vertica 可攜驗收）；完整隔離回歸更新為 841 passed／23 skipped／1 warning（20.67 秒）。QA 與正式 Release 仍未通過。

- 網站建立專案／上傳合成 CSV／需求補正／命名確認／SA 交接／Developer 規格核准／標準答案核准／Hop 排隊均實際操作，沒有攔截 API 或替代模型。Task `TASK-20260917-0007`，同一 Run `d8abcc97-e5d7-4f83-9d47-b244e03730e7`。
- SA、Developer 各 1 次真實 Copilot gpt-5.4 完成；QA 原始 1 次及使用者追加同意的 1 次均回覆 NEEDS_REVIEW。合計 4 次呼叫，用量與兩次 QA 歷史均已保存，沒有自動重試、換模型或工具操作。**不得寫成 QA／順序 3 通過。**
- 真實 Hop 執行一次，Vertica 結果精確多重集合 MATCH：預期／實際皆 3，缺少／多出皆 0；WRITE_STARTED、execution reservation、Hop completed 各 1。補正 QA 過程只有唯讀重查，不重跑寫入。
- 首次 QA 揭露 citation alias 說明不清；prompt v3 明確對應 semantic_design 與 context.semantics。追加複核進一步揭露缺少 CSV 契約、case-sensitive 排序與輸出型別的上下文；已補上 context v3，真實來源 70 bytes／7 筆重新驗證，與執行 source／HPL 指紋一致。尚未再交模型審查，不能推定 PASS。
- migration 049 新增明確授權的一次改版複核，舊 terminal 審查不可刪改，網站完整保留兩次 NEEDS_REVIEW。候選 ZIP／正式 Release API、網站與 replay Worker 已實作，但本 Run 仍受 QA 門檻阻擋，沒有 SDM／正式 ZIP 或可攜執行通過證據。**順序 4 未完成。**
- 完整隔離回歸 829 passed／23 skipped／1 warning（21.10 秒）；前端建置通過。這些不是模型或 Release E2E 通過證據。詳細記錄見 [順序 3、4 真實驗收進度](verification/p0-step-3-4-live-2026-09-17.md)。下方舊進度的 0／3、未部署及停用描述已被本節取代。

## 順序 3、4 開始實作（2026-09-17）

- 最新原始碼（尚未部署）：新增正式交付 SDM、不可變候選 ZIP／核准交付儲存、可攜證據與核准指紋驗證；migration 048 僅在隔離測試庫套用。正式交付 API／網站整合及可攜執行 Worker 尚未完成，不可視為可操作的 Release。
- 本批隔離回歸 811 passed／23 skipped（20.03 秒）：包含正式 SDM 映射保留、ZIP 固定成員與重現性、檔案完整性及可攜證據拒絕不符標準答案。後續檢視修正標準答案命名指紋讀取來源（執行授權沒有 naming_checksum，應使用已綁定 specification.naming.checksum），此整合分支仍待真實完整鏈測試。
- 真實 SA／Developer／QA 本次仍為 0／3 次；未進行新 Run 的模型或 Vertica 寫入，沒有正式 Release 或可攜驗收通過證據。下一步必須完成交付入口／隔離重播並驗證同 Run 完整操作，不得以以上回歸數字代替順序 3、4 驗收。

- 最新部署（本節前項優先）：QA context v2／prompt v2、網站 QA 授權及 Hop 單次排隊（migration 047）已部署，API healthy。Copilot／Hop 派發仍停用，僅控制 Worker 運行；3 次真實模型額度均未使用。
- 新增 QA authorization GET／POST，確認 comparison/context/prompt/schema/model 後僅保存呼叫意圖；本機 QA worker 的 --website-authorized 模式只領取已授權紀錄，不新增隱含同意。既有直接單次 CLI 授權路徑保留。
- Hop 網站派發綁定 SA trace／人工交接、Developer 保存規格、規格與標準答案核准及 DDL；新 Request 歸屬既有 Run，不另建 Task。單次 claim、不可重播；Worker 僅新建 ai_sample 專用表，存在即拒絕，無 DROP／清空。完成後沿用原 Hop 引擎、空表與來源保護及受控結果比對。尚未進行本入口真實 Vertica 寫入驗收。
- 隔離 PostgreSQL 全套 802 passed／23 skipped（19.81 秒），含實際網站 API→PG 授權、重送同工作、單次領取、失敗不可重播與歷史不可刪改；角色為合成回應、沒有 ETL 寫入。後續修正 LiteLLM 既有 EXACT／UNAVAILABLE 用量 enum 相容，定向 24 passed（0.36 秒）。
- 部署後瀏覽器 4 passed（9.1 秒）：Developer、QA／Hop 授權、QA 歷史與既有 Task 六頁籤／下載／窄版；派發 API 為測試攔截，不可視為模型或 Hop E2E。追加原始碼在建立目標前檢查執行同意未過期（尚待下一批部署）。
- 接續：正式 Release 核准／保存下載及可攜驗證機制，然後同一新 Run 執行已核准的真實 SA／Developer／QA 各一次與完整網站→Hop／Vertica→交付驗收。順序 3、4 尚未完成。

- 最新部署：SA 人工交接、Developer 網站授權／回讀、單次 Windows bridge／worker 及 045／046 已部署；API healthy。Developer 派發預設 false，尚未啟動本機 Developer Worker，也沒有消耗本次 3 次真實模型額度。
- Developer 網站 API → 隔離 PostgreSQL 已驗證授權版本、拒絕缺確認／模型或 context 改變、同版本重送、不可重領、成功原子保存規格、過期／未知歷史；整批 782 passed／23 skipped（19.00 秒）。部署後瀏覽器 2 passed（6.3 秒），Developer 授權／保存重載／409／390px 及舊 Task 六頁籤下載回歸，模型 API 為合成攔截，非真實模型 E2E。
- 後續原始碼（尚未部署）：QA context v2 加入原始需求、Requirement Conditions、實際已執行規格及 HPL 節點映射；prompt v2 要求語意對照與節點引用，PASS 必須引用 semantic_design，不能僅依筆數。舊 v1 歷史仍可解析，不自動升級／覆寫舊核准。
- QA 新版定向 30 passed；最新隔離全套 788 passed／23 skipped（19.02 秒）。使用既有真實 Hop Run `7fc2be0d-f1a8-4ea5-a9ed-74107369001b` 唯讀重建語意上下文 2 passed（1.12 秒）：兩次一致、執行規格／節點存在、不夾帶連線欄位、跨 Run 比對拒絕。沒有新模型請求、QA 核准或 Vertica 寫入。
- 尚待：新版 QA 部署及網站派發、Hop 網站派發、同 Run 真實三角色驗收、正式 Release 核准與 ZIP 保存／下載／可攜執行。順序 3、4 仍未完成，以下未部署描述為較早進度。

- 本批進度：SA 人工交接 UI 已加入並通過前端建置；真實隔離 PostgreSQL／API 測試確認保存、重送、過期拒絕及不可變歷史。尚未部署，不算網站真實模型驗收。
- Developer 新增 gateway、journal、migration 046 與不可重領的單次 claim：成功結果與既有 specification 在同一交易保存；上游失效僅保留歷史、不產生新規格；結果不明禁止自動重送。沒有核准規格或啟動 ETL 的副作用。
- 隔離 PostgreSQL 全套回歸 776 passed／23 skipped（18.61 秒），包含 Developer 成功／過期／未知結果三條實際資料庫路徑，使用合成模型回應並回滾交接資料。045／046 僅在隔離測試庫套用，尚未部署 Pilot。
- 補上 Copilot 用量白名單保存（credits、premium requests、CLI 次數、重試／工具次數），未知 Token 不填零；QA 沿用歷史 nullable 欄位並保留新用量資訊。此後定向測試 21 passed，尚待完整回歸與部署。
- 尚未呼叫本次真實模型，3 次額度均未使用。接續仍須 Developer Windows bridge／網站派發與讀回、QA 語意上下文、Hop 網站執行及正式 Release 流程；順序 3、4 不可標為完成。

- 使用者已同意本次真實 Copilot 驗收；依提問範圍限制最多 3 次請求，SA／Developer／QA 各一次，不自動重試或換模型，不能保證 CLI 輸出 Token 硬上限。Profile 為 copilot-pilot-1789262095192，三角色既有路由皆 gpt-5.4。本批尚未呼叫模型，額度未消耗。
- 新增 SA 人工交接 binding、保存／回讀 API 與 migration 045（未部署）：只接受当前 READY_FOR_REVIEW 的 SA 結果，不能以輸入確認取代模型建議核准；綁定 input/settings/context/review，正常下游執行不將歷史核准誤標過期，但不能再次授權已寫入 Run。
- 新增 Developer 受控上下文與結構化建議契約（未部署）：要求已保存 SA 人工核准及已確認命名；排除來源路徑、機密及樣本內容，沿用 EtlSpecificationV1 deterministic validator，拒絕任意 SQL、改目標、改命名、改寫入模式及不明引用。SA／Developer 定向單元 20 passed（0.28 秒），不是真實模型或 DB 持久化验收。
- 下一步仍需：SA 交接資料庫／UI 驗收、Developer gateway／持久化／單次派發、QA 語意上下文、網站 Hop 派發及同 Run 三角色真實驗收；其後正式 Release 人工核准／保存下載與目標環境可攜驗收。顺序 3、4 尚未完成。

## 順序 1、2 驗收完成（2026-09-17）

- 順序 1：篩檢誤判修正已部署；真實 PG／保管庫候選封裝 6 passed，敏感內容負向回歸保留。正式 Release 尚未開放。
- 順序 2：隔離 PG 全套 740 passed／23 skipped；真實 Hop 寫入後、結果回報前中止 Worker，再重啟 PG／API／CONTROL，租約自然到期轉 NEEDS_REVIEW／HOP_RESULT_UNKNOWN，沒有重複寫入。真實瀏覽器核對結案 1 passed；設定／專案／版本操作 4 passed。
- 新中斷 Run `1b228586-f647-42ec-8572-ba12b1338d6c` 結案後仍保留原 outcome 與寫入標記，狀態 FAILED；Vertica 仍一列 A／301.35／2，WRITE_STARTED 與 reservation 皆為 1。舊授權重領、遲來成功回報均被拒絕；不授予 QA／Release。
- 詳細要求對照、實測時序、初次失敗、證據與限制見 [順序 1、2 驗收報告](verification/p0-step-1-2-acceptance-2026-09-17.md)。這不代表整體 P0–P3 或真實模型鏈已完成。

以下為歷次進度，未完成描述以最新驗收報告為準。

## 順序 1／2 進度（2026-09-17）

- 已修正 Release SDM 篩檢誤判：真實保管庫值只命中標準 OOXML 屬性名稱，未命中解析後的內容。改用 XML 解析與明確標準属性白名單；所有屬性值、非標準名稱、儲存格、註解、PI、實體解碼及拆分文字仍檢查，DTD 拒絕。未改憑證或豁免短機密。
- 真實 PostgreSQL／指定版本保管庫／合成 QA／SDM／候選封裝回歸 6 passed（1.69 秒），原先 5 passed／1 failed 已解除。全部核准測試交易回滾；候選不是正式 Release，沒有呼叫模型或寫入 Vertica。
- 新增 migration 044、GET／POST runs/{run_id}/reconciliation 與版本內容中的人工核對表單，已部署 API／網站／CONTROL。只允許失敗／未知 Hop 結果、無有效租約的版本結案；需明確確認引擎停止及目標核對，保存本機證據 SHA-256 與觀察筆數。證據檔不上传。結案不代表資料回復／QA 通過，不啟動重跑；原始 outcome、write_started、授權與 Log 保留。
- 定向單元 34 passed；完整後端 667 passed／96 skipped（7.15 秒）。真實 PG 人工核對 API 2 passed（1.23 秒），含冪等、409、404、缺確認拒絕、歷史不可改寫、失效完成拒絕與 WRITE_STARTED 次數不變，全部回滾。此為既有 Run 上的合成失敗狀態，不是真實中斷驗收。
- 部署後瀏覽器 2 passed（8.4 秒）：人工核對確認／證據指紋／保存重載／衝突／390px（合成 API）及既有 Task 六頁籤／下載回歸。前端建置通過；未結案實際 Run。
- 順序 2 尚未完成：真實執行途中程序中止／服務重啟／不重複寫入，以及真實網站 → API → DB 人工核對正向連續驗收；仍需隔離環境完整跑設定優先序及重複請求回歸，不可把目前局部測試拼成全流程成功。

以下為歷史紀錄；9 月 13 日的封裝失敗已由上述修正解除，未完成項目以新段落為準。

## 當前判定（2026-09-13，真實目標歸屬與來源證據已顯示）

- 候選封裝新增 Run-scoped vault 篩檢（未部署）：核對設定與 AI Profile 版本，讀指定版本連線／AI 機密，僅記憶體比對、結束清空列表，不回退最新憑證；不掃無關帳號。單元測試 8 passed（0.08 秒）。
- 真實 PG／保管庫整合目前 5 passed／1 failed（1.39 秒）：RELEASE_DEPLOYMENT_VALUE_FOUND，候選封裝停止。尚未判定是實際洩漏或比對誤判，不能視為成功。未放寬規則、修改憑證、發布 ZIP 或輸出機密；下一步需安全定位比對來源。

- 新增內部 assemble_release_candidate（未部署）：同 Run 有效 QA、QA-linked SDM，從 deterministic compiler 重建 HPL／HWF／DDL／參數；HPL 核對 execution authorization，DDL 核對驗證後 target claim。讀取 SDM bytes、內容篩檢後建立六個固定成員候選 ZIP，沒有任意歷史檔案選取。
- 真實 PG＋合成 QA／實際 SDM／候選 ZIP 及篩檢回歸 12 passed（1.50 秒）。過程修正 DDL 指紋來源及 http XML namespace 誤判磁碟路徑。ZIP 只在測試記憶體，交易回滾；沒有正式下載、機密 vault 完整篩檢或目標環境執行證據，Release 仍 false。

- 新增 Release content screen 原始碼：檢查固定五類產物，XLSX 解壓後檢查 XML／rels，不跳過試算表；限制展開大小及數量、檢查部署值（含 XML entity 轉義）、常見絕對路徑與本機 host。5 項單元測試通過（0.04 秒）。尚未串接封裝服務或部署。
- 內容篩檢只回 CONTENT_SCREEN_PASSED／portability NOT_VERIFIED，不證明所有機密已排除、沒有提供部署值集合或可攜執行驗收，也不授予 RELEASE_READY。正式 controller 產物解析與核准封裝仍待完成。

- SDM 交付準備 API／migration 043／交付頁已部署，API healthy。有效人工 QA 才可產生／取得 QA 關聯 SDM，保留原歷史文件下載；版本衝突清除成功訊息與可操作狀態，Release 仍未開放。
- 前端建置通過；部署後瀏覽器 2 passed（6.4 秒）：合成 API 交付條件／成功／409／390px，加上舊 Task 六頁籤、產物與下載契約回歸。沒有實際新增文件或核准；此前真實 PG＋合成 QA／文件測試與此次 UI mock 不能合併宣稱真實模型端到端驗收。

- SDM 交付準備已整合為同一 DB 交易：有效 QA → 同 Run SDM 保存／驗證 → QA 關聯。新增 POST /api/tasks/{task_id}/runs/{run_id}/sdm-delivery，只收 qa_binding_checksum，不接受檔案路徑；版本衝突 409，Release 仍 false。原始碼尚未部署／接前端。
- 真實 PG＋合成 QA／實際 SDM 回滾測試 6 passed（1.25 秒）；API／SDM 定向測試 8 passed（0.51 秒）。失敗交易可能留下無 metadata 的孤立檔案，既有下載要求 DB metadata，故不可下載；尚未提供自動清理。沒有實際核准或交付記錄。

- SDM／QA 關聯已補上實體檔案驗證（原始碼尚未部署）：安全讀取、大小與 checksum，再以同 Run 規格及 Naming Contract 驗證 XLSX 內容；重送也重新驗證文件。metadata-only 候選無檔案時拒絕，不再只憑資料表記錄關聯。
- 定向單元測試 6 passed（1.03 秒）；真實 PG＋合成 QA 及實際 SDM 生成／讀回／關聯冪等／無檔案拒絕回滾測試 6 passed（1.20 秒）。未留下實際核准、SDM metadata 或 QA 關聯；版面沿用前批已驗證 renderer。網站交付入口與 Release 仍未完成。

- 同 Run 執行後 SDM 實際產生／保存／冪等／下載讀回已在真實 PostgreSQL＋合成 QA 核准回滾交易驗證，6 passed（1.26 秒），persisted write_started 仍 true。使用原 renderer 與內容 validator，未重新執行 Hop。
- 驗證副本位於 outputs/sdm-post-hop-verification/post-hop-candidate.xlsx，非註冊交付產物；QA 與 metadata 全部回滾。Artifact Tool 獨立匯入確認兩頁、三個輸出欄位及 amount GT 100／SUM／COUNT；兩頁已渲染並人工視覺檢查，主要內容與完整指紋可讀。圖片工具初次 sandbox 錯誤後以唯讀圖片資料完成檢視。
- 候選文件仍明示未交付且不含核准結果；此測試不能算真實模型或 Release E2E。save_delivery_candidate 與 043 尚未部署／接網站，正式 QA 關聯與 Release ZIP 仍待完成。

- 新增 save_delivery_candidate 原始碼：已完成 Hop 的同 Run 必須具有效人工 QA checksum，重新核對規格核准，再沿用既有 SDM renderer／保存邏輯。原 save_candidate 仍保留執行前限制；只在文件驗證用副本調整 write_started，不改 DB 或重新執行 Hop。產物仍 CANDIDATE_NOT_RELEASED，尚未串接 QA 關聯及公開 API。
- 拒絕路徑單元測試 2 passed（0.49 秒）：無 QA 核准或 checksum 改變時不呼叫 renderer。尚未部署或實際生成 XLSX，不能算成功文件 E2E。依 Spreadsheets skill，後續仍需產出內容與視覺驗證，保留既有版面，不另建 renderer。

- SDM／QA 關聯真實 PostgreSQL 回滾測試已加入：migration 043 在交易內建立、metadata 正常關聯、跨 Run trigger 拒絕、冪等、UPDATE／DELETE 不可變。整批 QA／交付 metadata 測試 6 passed（1.09 秒），全部回滾，沒有 XLSX 文件或正式核准紀錄。
- 此驗證只涵蓋 metadata；043 尚未正式部署。真正 SDM 內容驗證、執行後同 Run 文件生成／下載，以及 Release ZIP 尚未完成；不能將 synthetic-metadata-no-file 視為可下載產物。

- 新增 SDM／QA 不可變關聯原始碼（migration 043、sdm_qa_binding，未部署）：沿用既有 SDM 候選，不覆寫文件；同 Run、Project、Task、規格 checksum 與有效 QA binding 才可關聯。此狀態為 QA_LINKED_NOT_RELEASED，不驗證文件位元內容、不授予 Release。
- 關聯版本拒絕／候選檢查／冪等單元測試 4 passed（0.24 秒，mocked store）。資料庫 trigger、真正文件內容及同 Run 產生／下載仍待整合驗收。未生成 XLSX、未改既有資料或新增模型用量。

- 核准整合後完整後端回歸 625 passed／94 skipped（5.96 秒）。新增執行後 delivery_context（尚未部署）：要求 APPROVED_CURRENT，重新核對實際執行 specification 與人工 QA binding；提供後续 SDM 使用的綁定輸入，不生成檔案、不授予 Release。真實 PG＋合成 QA 核准回滾测试 6 passed（1.06 秒）。
- 已確認現行 SDM save_candidate 只走執行前 load_approved_candidate；尚未將新交付入口接入 SDM renderer／metadata。不能將上述上下文驗證當成 SDM 或 ZIP 已完成。

- migration 042、核准 API、QA journal 一致回讀與 QAApproval UI 已一起部署，API healthy。瀏覽器 2 passed（4.9 秒）：合成 API 的確認／提交／保存後重載／409 清除，加上 QA 歷史狀態與 390px 回歸。提交被測試攔截，沒有核准實際 Run。
- 部署後真實既有 Run 回讀為 NOT_ELIGIBLE，QA journal 與獨立核准回讀一致，qa_review_approval 筆數 0。這證明部署與拒絕／合成互動正常，仍不是實際模型 PASS 到人工核准的完整 E2E；模型鏈、同 Run SDM／Release、P2／P3 仍未完成。

- 新增 QAApproval 前端並嵌入既有 QA 審查頁：獨立顯示人工核准／歷史失效、版本指紋、明確 checkbox、提交與重新讀取；載入或提交失敗清除舊 binding，不沿用可核准狀態，切換 Run 重建元件。pnpm run build 通過（TypeScript＋Vite）。
- 此批前端／migration 042／核准 API 尚未部署；建置不等於按鈕驗收，仍需瀏覽器確認、409、刷新、窄版面及舊 QA journal 狀態一致性測試。没有實際人工核准或模型呼叫。

- QA 核准 GET 已改為狀態回讀（尚未部署）：NOT_ELIGIBLE／AWAITING_CONFIRMATION／APPROVED_CURRENT／STALE_APPROVAL。保存紀錄重新核對 binding checksum 與 Run／invocation；歷史失效仍保留 approval metadata，但 qa_approved=false、release_ready=false。API／純狀態測試 10 passed（0.38 秒），真實 PG＋合成 provider 保存回讀回滾測試 6 passed（1.00 秒）。
- QA journal 原唯讀回應與前端尚待切換至此人工核准狀態；不可只部署 API 就宣告畫面一致或完整人工 E2E 已完成。本次無真實模型用量、無實際核准保存。

- 新增 GET／POST /api/tasks/{task_id}/runs/{run_id}/qa-approval（原始碼，尚未部署）：取得版本 binding，提交 StrictBool confirmed 與 checksum；過期版本回 409，其餘錯誤遮蔽。Release 固定 false。QA 核准／原唯讀 API 定向測試 12 passed（0.41 秒），使用 mocked store；資料庫保存證據另見前批回滾測試，不算 API 到資料庫 E2E。
- 仍待整合 QA 頁面的確認、核准狀態回讀與版本失效呈現；migration 042 與 API 暫未部署，避免目前唯讀頁尚未反映人工核准而產生矛盾。

- QA 人工核准保存已加入原始碼（migration 042，尚未部署）：同 Run 單一不可變核准、Operator、完整版本 binding；明確 confirmed 才能保存、checksum 不符拒絕、同版本重送回同一 approval。寫入 QA_HUMAN_APPROVED 事件，但不變更 Release Ready。API／網站與後續 SDM 尚待整合。
- 真實 PostgreSQL 回滾測試 6 passed（0.97 秒），包含建立新核准表、合成 QA PASS 核准、無同意拒絕、版本衝突、冪等、UPDATE／DELETE 拒絕；全部回滾，沒有核准實際 Run 或留下測試 schema。未呼叫模型。此結果仍不是完整人工操作 E2E。

- 新增 QA 人工核准 binding（原始碼，尚未部署）：從現行 Run 與不可變審查紀錄建立 Project／Task／Run／輸入／設定／規格／context／review 指紋；僅 VALIDATED_NOT_APPROVED 且 PASS、當前版本與完整證據可產生 offer。未知結果、上游過期或 context 改變拒絕。此 offer 不是核准紀錄，不變更 qa_approved 或 Release 狀態。
- 真實 PostgreSQL＋合成 provider 回滾測試 6 passed（0.95 秒），增加 offer 一致性、未知結果與過期拒絕驗證；沒有保存人工核准，也沒有模型請求。仍需核准持久化／API／UI 與同 Run SDM／Release 整合，完整 P1–P3 未完成。

- Copilot QA adapter／本機橋接已部署到 API／Worker 映像，API healthy；未啟動本機 QA 模型 Worker，派發維持關閉。Windows 真實傳輸至 WSL／Docker：無同意回傳 QA_MODEL_CALL_CONSENT_REQUIRED、停用回傳 QA_DISPATCH_DISABLED，兩者均符合預期。只公開白名單阻擋碼，其餘例外遮蔽。
- 定向合成回歸 17 passed（0.30 秒）；部署映像真實 PG 派發／超時／非 Copilot Profile 拒絕測試 6 passed（0.80 秒）。既有合成 Profile 的 Run 不會被當成 Copilot，拒絕時不新增 QA 意圖。以上證明拒絕路徑與 journal 防護，不代表原生成功呼叫 E2E；仍需正確綁定 Copilot 的 Run、額外模型用量同意及真實成功保存驗收。沒有修改既有 Run 設定、Vertica 或歷史產物。

- 新增 local_qa_bridge／local_qa_worker 原始碼：指定 Task／Run／comparison／context checksum 及明確模型同意，領取沿用不可變 qa_dispatch_claim；Windows 僅收到必要 QA context、模型及精簡 Run，不回傳 DB 設定或機密。呼叫前檢查 claim／版本，完成後交由 QAJournal 驗證保存；失敗轉未知結果，不重送。沒有常駐掃描或自動派發。
- 本批完整後端 614 passed／93 skipped（5.88 秒）。新增 Worker 合成測試驗證同意、停用開關、單次成功／失敗流程；尚未部署、未完成真實跨 Windows／Docker 橋接整合或模型驗收，不能算完整 P1。未啟動新 Worker、未消耗模型額度。

- Copilot QA adapter 已在原始碼補上：共用既有 CLI 工具禁用入口，接受 QA specification checksum，不再硬取 SA input checksum；QA gateway 驗證固定模型、Run、context、prompt/schema 與結構化結果，失敗不重試。必須由原生 Worker 提供領取／版本檢查 callback；未提供即拒絕，沒有改成 Docker 自動呼叫或模型 fallback。
- 此 adapter 尚未部署或接上原生 QA Worker／網站。合成定向測試 18 passed（0.21 秒），完整後端 610 passed／93 skipped（5.80 秒）；未呼叫真實 Copilot，不算真實角色或完整 P1 驗收。

- QA 內部派發與過期收尾已部署（migration 041）：不可變單次領取紀錄阻止重送；CONTROL 將已領取且超時的 QA_RESERVED 收尾為 QA_OUTCOME_UNKNOWN，不呼叫模型、不自動重試、不授予 QA／Release 核准。未領取的意圖不當成模型超時。Copilot 原生 QA 接點、公開派發與人工核准仍未完成。
- 本批後端回歸 606 passed／93 skipped（5.80 秒）；真實 PostgreSQL＋合成 provider 交易回滾測試 5 passed（0.86 秒），包含成功／失敗不可重送、重複領取拒絕、未過期保留及過期只收尾一次。不是實際 QA 模型驗收。部署後 API healthy，QA invocation／claim 均為 0，execution／SA／QA dispatch 均關閉。
- 本次重新唯讀確認 Vertica 25.3 容器健康、平台保存連線可查詢，既有合成結果 A／301.35／2；未刪除或重建資料庫。Run 仍 NEEDS_REVIEW。P1 完整角色模型鏈、網站執行、QA 人工核准、同 Run SDM／Release，以及 P2／P3 均未完成。

- QA 紀錄唯讀 API 與「執行與 QA」頁已部署：呈現模型、用量、版本證據、建議及未知／過期狀態；API 回傳前核對 context、review 與 trace 綁定，不公開完整 prompt 或設定。正式派發與人工核准仍不可操作且有原因說明。
- 本批次 QA API／契約單元測試 22 passed（0.38 秒）、真實 PG 審查保存與回讀回滾測試 2 passed（0.75 秒）、瀏覽器 3 passed（8.5 秒）。瀏覽器含真實來源證據＋尚無 QA 紀錄、合成 QA 狀態／錯誤清除／390px，以及合成歷史產物回歸；未呼叫模型，不能當成真實 QA Agent 驗收。

- QA journal 已沿用 agent_invocation 部署（migration 040）：單 Run 意圖、固定 context／prompt／schema、結果追加與不可變歷史；未知結果保留 QA_OUTCOME_UNKNOWN，不重置為可重送。正式 QA 派發與 API／網站核准仍未接通。
- 本輪完整後端回歸：599 passed／88 skipped（6.00 秒）；真實 PostgreSQL＋既有 Hop 證據、合成 QA 回應的回滾測試：4 passed（0.86 秒）。確認 QA 紀錄數仍為 0，沒有把合成模型回應留在實際案例中。API healthy，execution／SA dispatch 仍 false；未呼叫任何模型。

- QA context 已從指定 Run／比對 ID 讀取已保存的規格、重建 HPL 指紋、流程圖檢查、解密 Hop 節點摘要與來源紀錄。新真實 Run 五類程式檢查 PASS；舊 Run 來源 MISSING。唯讀 PostgreSQL／私有日誌整合測試 2 passed（0.69 秒），未呼叫模型或授予 QA 核准；尚未接入持久化審查及網站。

- QA gateway 已接入共用 Model Gateway 的 `qa_review` 路由；核對 Run 狀態、版本與固定模型，不做模型 fallback。成功／失敗回傳 prompt/context/output 指紋、耗時與可取得的用量，尚未持久化。QA contract＋gateway 合成測試 17 passed（0.19 秒）；沒有真實模型呼叫、尚未部署或接入網站審查。

- QA 角色契約已開始實作：固定五類程式證據、版本與 context checksum、證據引用，以及程式 FAIL 不可被模型 PASS／NEEDS_REVIEW 覆寫。9 項單元測試通過（0.14 秒）。目前僅原始碼與測試，尚未接入模型、持久化審查或網站人工核准；不能當成 QA 完成。QA PASS 明確只為建議。

- 新 Run `7fc2be0d-f1a8-4ea5-a9ed-74107369001b` 已完成：目標登錄、真實空表檢查、一次 Hop 寫入、綁定查詢比對 MATCH，另以獨立連線核對 A／301.35／2。
- 既有 QA 比對頁已顯示「來源已核對（平台管理目標）」；舊無執行前證據的 Run 不能事後補升級。這是來源證據，不是 QA 人工核准或 Release。
- 最新後端整批 582 passed／84 skipped（5.86 秒）；目標／空表 PostgreSQL 約束 1 passed（0.36 秒）；網站局部 2 passed（6.4 秒）。詳見 [真實 Run 與網站證據](verification/bound-target-native-2026-09-13.md)。
- API／CONTROL／網站已更新至 migrations 039，執行與模型 dispatch 仍關閉。下一步為正式 QA 決策與人工核准、同 Run SDM／Release，以及網站派發；P1、P2、P3 仍未完成。

### 前次判定（目標歸屬保護）

- 使用者已確認本機 WSL Vertica 為測試資料庫；健康且可用，沒有刪除重建。平台保存的連線已接通，TLS 沿用使用者原設定。
- 真實 Hop→Vertica 首次成功，Run `65269428-7e6c-434b-a16e-5d557608f184`；結果 A／301.35／2。執行前查詢 checksum、Run 連線快照與指定版本機密重新讀取比對為 MATCH。詳見 [真實結果證據](verification/native-vertica-success-2026-09-13.md)。
- 新增不可轉移的 Run 目標登錄；同 schema/table 不得跨 Run 重用，且拒絕寫入後補登。真實 adapter 寫入前強制檢查，範例重建入口拒絕已登錄目標。此為平台內隔離，不宣稱能防止外部 DB 管理者直接改資料。
- Migration 037 已套用，API／CONTROL 與 Worker 映像已更新；ETL 與 SA 自動執行仍關閉。舊成功 Run 未補登，其 QA／Release 仍未核准。
- 本輪完整後端回歸：567 passed／84 skipped（5.66 秒）；真實 PostgreSQL 約束與遷移測試：4 passed（1.06 秒），合成資料全部 rollback。最初兩項過時 CLI mock 不接受新參數，修正並加入 launcher 分支測試後整批重跑通過。
- 部署後網站局部回歸：4 passed（10.5 秒），涵蓋專案新增／編輯／取消／重載、歷史 Task／節點／返回，以及合成設定草稿與歷史下載／窄版面契約。初次 1 failed／3 passed 為舊 Release 提示文字斷言，核對實際畫面後更新並保留禁止下載檢查；不是全網站或 ETL E2E 驗收。
- 仍需新 Run 實跑目標歸屬流程、空表與結果來源完整驗證、正式 QA 核准、網站派發及同 Run SDM／Release；P1、P2、P3 均未完成。

### 前次判定（SDM 候選文件部署後；以下連線描述為歷史）

- SDM openpyxl renderer、不可變版本 metadata、受控檔案保存與生成／下載 API、Task 規格頁按鈕已部署。文件仍為 CANDIDATE_NOT_RELEASED，不能當成正式交付。
- 本次後端整批回歸：534 passed／81 skipped（5.63 秒）。本次網站整批回歸：29 passed／2 skipped（約 1 分鐘），包含真實 SDM 生成下載、API metadata 回讀；合成回應測試與真實流程分開標示，未呼叫模型或 Vertica。
- 本次真實 SDM 網站證據：TASK-20260913-0284，Run aa9a3415-d716-4585-9265-d7b3c1b94ff1，規格 7dd76022-4ea0-4983-b3fd-7d6b2836d76b。另有儲存 API＋PG 整合測試通過，涵蓋錯誤版本、重複保存及檔案遭修改時拒絕下載。
- 使用者已同意 openpyxl；Vertica 設定及加密密碼已保存，但容器 API 對設定的 loopback 位址 TCP 連線遭拒。預期目標是否為本機 vertica-25.3 及測試寫入範圍仍待確認。不得自行切換目標或降級 TLS。
- SDM 歷史、交付頁 Run 選擇與下載、保存時間線均已部署。TASK-20260913-0291 的瀏覽器驗收與既有六頁籤／歷史下載回歸共 2 passed（8.6 秒）；第一次因舊提示文字斷言失敗，更新文字後重跑，Release 阻擋檢查未放寬。這是局部回歸，不取代上述整批結果。
- PostgreSQL 改版測試確認：新規格保存後，舊 SDM 仍可查詢下載，但舊核准不能再生成文件。重複取得文件不重複新增保存事件。
- P1 真實 Hop→Vertica→QA→SDM→Release、P2 四情境、P3 20 案例與人工基準均未完成，完整交付核准鏈仍待補齊。
- 目前重新讀取部署設定：API ready、execution_enabled=false、vertica-default Port 5433、host 仍為 loopback。尚未取得目標確認，不自行換成另一個容器或主機位址，也未新增模型呼叫或 Vertica 寫入。

### 上一批次：查詢指紋部署時的判定（保留歷史）

- API ready、execution_enabled=false；沒有新增模型呼叫或 Vertica 寫入。
- Project 最新 Run 摘要、設定錯誤中文指引、Task 版本讀取失敗清除舊核准內容均已部署。專案摘要不是 QA／Release 成效統計。
- 查詢計畫已接入已核准候選與執行授權；執行後載入答案會拒絕缺少查詢指紋的授權。歷史資料未補簽或修改，既有歷史讀取仍保留。尚未證明 Run 專屬目標及查詢來源。
- 最近安全後端整批回歸為 513 passed／78 skipped；後續查詢指紋格式檢查另有 9 項單元測試及 PostgreSQL 搭配合成 Hop 結果 3 passed／1 skipped。這些不是同一整批執行，不可累加成完整 E2E。
- 最近網站整批回歸為 29 passed／2 skipped（約 1 分鐘），已包含設定提示與版本切換。首次執行因合成歷史測試漏接摘要 API 而有 1 項失敗；補齊測試回應後完整重跑。詳見 [網站合併回歸](verification/workspace-regression-query-binding-2026-09-13.md)。
- P1 真實 Hop→Vertica→QA→SDM→Release、P2 四情境與 P3 20 案例／人工基準仍未達成。正式 SDM renderer 工具選擇待使用者確認；可用 Vertica 連線及批准的測試寫入範圍仍待確認。

## 歷史批次摘要（以下數字及部署描述僅代表當時，不是目前最新）

最新整批回歸：[答案／比對合併驗收](verification/combined-oracle-regression-2026-09-13.md)：網站 26 passed／2 skipped、後端 397 passed／73 skipped、隔離 PG 60 passed／1 skipped、原生 Hop 4 passed。四類範圍不可累加，也不代表真實 Vertica／QA／Release 驗收。下方較早測試數字保留為批次歷史。
最新完整網站回歸為 25 passed／2 skipped（50.8 秒），詳見 [答案表單驗收](verification/oracle-editor-ui-2026-09-13.md)。後續歷史答案回讀、型別邊界及執行授權綁定另做局部回歸，不能視為再次完整套件驗收。最新安全後端回歸 382 passed／73 skipped（5.20 秒），不包含真實外部模型或 Vertica。

答案管理已部署欄位輸入、保存、人工核准、歷史唯讀回讀及型別限制；[單次執行授權 v2](verification/oracle-execution-binding-2026-09-13.md) 已綁定答案版本與核准。新增內部 execution_oracle 依完成 Run 的不可變授權讀取指定答案，不選最新答案；隔離合成 Worker 測試 3 passed／1 skipped（1.53 秒），尚未部署此新函式或接入真實結果比對。QA、SDM、Release 仍未完成。

執行狀態澄清：已具備內部單次 Worker／Hop adapter 與加密 Log 保存；[原生初始化失敗路徑](verification/native-worker-failure-2026-09-13.md) 曾實测，但尚無正式網站派發及真實 Vertica QA／Release。下列早期批次中的「尚無 Worker 呼叫／實際 Hop 派發」是當時狀態，不代表目前內部測試能力；正式執行開關仍關閉。
以下「已完成調整」各節保留當時的限制；若後续批次已補齊，應以最新調整與階段門檻為準，不能將歷史限制當成最新狀態。

寫入前強制檢查已部署：begin_external_write 現在必須核對部署開關、單次 reservation、授權有效期、租約及當前版本／準備指紋，輸入核准不能繞過。21 項 PostgreSQL 回歸通過；只驗證控制標記，尚無實際 Hop／Vertica 派發。

單次領取基礎：migration 031 新增不可變 reservation，將授權消耗、Run 租約及事件放在同一交易；19 項 PostgreSQL 測試通過，含競爭領取與失效後不可重用。沒有 Worker 呼叫入口／實際 Hop 派發，平台執行仍關閉；過期邊界與外部寫入前再次核對待驗證。

執行授權基礎：migration 030 新增獨立不可變授權，綁定 Run／規格核准／input／settings／HPL／來源 checksum，單次嘗試、禁止自動重試、30 分鐘有效期；18 項 PostgreSQL 回歸通過。僅內部函式與 schema，沒有 UI／API 派發入口，也沒有真實寫入授權紀錄。Worker 消耗與過期派發拒絕仍待接通。

最新合併回歸：本機 249 passed／52 skipped；隔離 PostgreSQL 所有 *_integration.py 共 51 passed。原生 Hop staging 另有先前實測，不混入此輪數字。詳見 [合併回歸範圍](verification/backend-regression-2026-09-13.md)。P0–P3 狀態不因此改為完成。

| 階段 | 狀態 | 尚未達成的驗收門檻 |
|---|---|---|
| P0 | 進行中 | 模型執行中斷的完整驗收與人工核對、Bedrock 真實驗收；專案摘要、設定連線測試紀錄與完整重啟驗收。專案／AI／分組設定／工具路徑與機密的離頁保護已加入；CONTROL Worker 已部署，Copilot 單次 SA UI→DB 已實測，非 ETL 成功 |
| P1 | 未達標 | 第一條 CSV→Hop→Vertica→QA→Release 成功案例，以及建立 Task 四步驟；Task 六頁籤已接上既有資料，未完成的新引擎／交付功能仍明示限制 |
| P2 | 未達標 | 四情境完整證據、Join 語意攔截、失敗診斷及人工核准重跑；專案 Pilot 評估頁 |
| P3 | 未完成 | 20 案例、人工基準與真實成效報告、主管報告匯出、完整指南與舊元件收斂 |

## 最新調整：來源檔案完整性 Gate

- 已核准來源準備整合：execution_preparation 將資料庫核准規格、重新驗證來源、副本與 HPL checksum 串接，副本後重新驗證版本；11 項 PostgreSQL 測試通過，含準備期間取消後拒絕交付並清理。尚無原子派發／Hop 寫入授權，本次只測新映像，運行服務未更新。

- P0 寫入不確定狀態：租約失效且 write_started=true 時保存 HOP_RESULT_UNKNOWN，事件明示可能已寫入且禁止自動重試，網站顯示人工核對警示。17 項 PostgreSQL 與 1 項合成 UI 分支測試通過，已部署；尚未實測真正 Hop 中断，也沒有人工結案入口。

- 執行前版本準備：approved_candidate 沿用 Task／Run／Naming 鎖與規格驗證，僅從目前已核准規格編譯候選。9 項 PostgreSQL 回歸通過，無核准／新命名／新規格均阻擋。尚未連接 dispatch 或開放執行；本次僅測試映像，運行服務未更新。

- 原生 Hop staging 驗證通過（5.88 秒）：副本建立後更改原始合成上傳檔，Hop 2.12 仍讀取唯讀副本產出固定 3 筆。network=none、TableOutput 在測試中換成收集器；這不是 Vertica 或平台 Worker 的執行驗收。

- P1 staging 開發中：新增單次讀取／驗證後的 attempt-local CSV 副本，31 項本機測試通過，原檔異動不影響副本。尚未接入原生 Hop 測試或部署 Worker；不構成 immutable runtime／ETL 驗收。

- CSV 換檔表單已部署：新檔預覽、確認、取消及新 Run 重新核准。真實 UI→API→Worker 證據回讀通過，完整網站回歸 12 passed / 2 skipped（40 秒）。限符合修訂條件的單一 CSV；不含 Excel／JSON、已取消或設定失效版本的換檔。

- 單一 CSV 換檔後端已接到既有 Run revisions API，31 項本機與 19 項 PostgreSQL 回歸通過；保留舊 Run／核准／檔案，新版須重新確認，錯誤檔案回滾。後端已部署，網站換檔表單與專屬 UI E2E 尚未完成，不能視為可操作交付。

- 歷史來源保護：停用按資料夾時間直接刪檔的 cleanup_expired，避免上傳／舊 Worker 清除被 Run 引用的來源。保留天數目前僅為 metadata，尚無引用感知清理，磁碟不會自動釋放；39 項本機回歸及部署後真實上傳測試通過。換檔修訂尚未實作。

- Task「需求與規格」新增來源驗證面板：大小、CSV 掃描筆數、完整性、失敗說明及可展開 SHA-256；明確標記歷史證據不是即時檔案狀態或 ETL 成功。部署後 11 項瀏覽器回歸通過、2 項跳過，含實際上傳面板與 390px 無水平溢出檢查。

- 上傳介面保存 size；CONTROL Worker 依已核准 Run 的 upload_id／checksum／size 讀取受控檔案，將 byte／CSV 結構證據寫入 gate_result。變更、遺失或綁定不全會停在 NEEDS_INPUT。
- 本機 37 項測試、隔離 PostgreSQL 19 項測試通過；部署後瀏覽器 10 項通過、2 項明確跳過。詳見 [來源完整性驗證](verification/source-integrity-2026-09-13.md)。
- 上傳 UI→共用 volume→Worker 專屬 E2E 已通過；發現並修正 repository 丟棄單一 sources 清單的問題。最新瀏覽器 11 passed / 2 skipped，含真實上傳補正及既有歷史頁面回歸；不等於 Hop 使用相同 byte snapshot，執行開關保持關閉。

## 最新盤點：Vertica 真實整合前置條件

- 本機 Vertica 25.3.0-2 與 Hop 2.12 容器運行中；Workbench／Hop／Vertica 分屬不同 Docker 網路。
- 平台 etl_qa 目前仍為字串，未具备 resolver 要求的結構化連線；需要確認測試目標並設定專用連線，不能沿用開發機隱含預設。
- [唯讀證據與待確認事項](verification/vertica-integration-prerequisites-2026-09-13.md)。未變更網路、讀取密碼或寫入 Vertica。

## 已完成調整：命名版本併發保護

- 命名保存現在與規格／Run 審查共用 Task-first lock，並回傳本次保存的 contract_id，避免版本配置競爭或回傳其他請求內容。
- 26 項 PostgreSQL 測試通過，包括實際平行保存及 pg_stat_activity 鎖等待確認；部署並確認 ready 後真實規格 UI 流程再次通過。首次緊接部署的 UI 失敗另記錄，不隱藏。
- [證據與限制](verification/naming-concurrency-2026-09-13.md)。執行流程與整體 P0–P3 仍待完成。

## 已完成調整：原生驗證來源的版本控制完整性

- 修正 `hop/` 忽略規則誤排除 scripts/hop 的問題，精確放行 8 個 Java／合成 fixture 依賴，敏感及未知資料維持排除。
- Git 規則測試、46 項規格／編譯測試及原生 Hop 7→4→3 列處理再次通過。尚未 commit／push，不代表 GitHub 已更新。[證據與限制](verification/native-source-distribution-2026-09-13.md)。

## 已完成調整：真實規格 UI 控制流程驗收

- 已完成無 API mock 的規格建立→保存→核准→重載→編譯預覽→協作時間線；正式 PostgreSQL 另確認規格／核准／事件與零模型呼叫、零 Hop artifact。
- 真實驗收抓到命名確認缺 confidence 時 500，已加輸入 schema 修正為 422；6 項單元測試與真實 API 回歸通過。全站 10 passed、2 opt-in skipped。
- 測試恢復原連線並取消 Run、保留歷史。仍未做 Naming UI 或 ETL／Vertica／Release E2E。[完整範圍與證據](verification/specification-real-ui-2026-09-13.md)。

## 已完成調整：欄位式規格建立／編輯

- 新增 editor-context 與規格建立／編輯表單，從當前 Run／Naming 取得內部版本綁定，人工選擇篩選／分組／聚合／輸出順序，保存後仍待核准。
- 已部署；42 項本機、容器 9 項（7 PostgreSQL API＋2 純 context）、全站 9 項瀏覽器回歸通過。新規格表單使用合成 API 回應，不能算真實 UI→DB 核准驗收。
- [證據與限制](verification/specification-editor-2026-09-13.md)。下一步補真實 UI 保存／核准連續案例及執行接線。

## 已完成調整：規格操作協作時間線

- 規格保存／人工核准已接入既有 Run event，記錄版本、checksum、核准與操作人員參照；協作頁可查閱，不把歷史核准當成目前執行權限。
- 26 項 PostgreSQL／Run／migration 測試及部署後 9 項網站回歸通過；重複保存／核准不新增重複事件。新 UI 事件顯示仍為合成回應驗證。
- 服務 ready、執行關閉；[證據與限制](verification/specification-timeline-2026-09-13.md)。規格建立／編輯與真實端到端核准仍待完成。

## 已完成調整：規格歷史與核准 UI

- Task「需求與規格」新增欄位式規格歷史、明確確認後核准、Hop 候選預覽；失效核准保留並停用操作，不呈現為 ETL 成功。
- 建置及部署完成，9 項網站回歸通過（新規格互動為合成 API 回應）；另 6 項真實 PostgreSQL API 測試確認 reviewable 與版本失效。兩項 opt-in 測試 skipped。
- 規格建立／編輯表單與 UI→真實核准 DB E2E 尚未完成。[證據與限制](verification/specification-ui-2026-09-13.md)。

## 已完成調整：規格版本保存與人工核准 API

- migration 028 擴充既有 specification 表，提供保存、歷史、checksum 綁定核准 API；已部署隔離 Pilot。新規格與上游異動使舊核准無效，歷史保留。
- 62 項本機、26 項 PostgreSQL／migration／Run 整合、部署後 8 項網站回歸通過；2 項 opt-in skipped。Worker 已恢復，ETL 執行仍關閉。
- 尚待網站規格編輯／核准、協作時間線及 Worker 下游重新查核接線；不代表 ETL／Release 成功。[證據與限制](verification/specification-revisions-2026-09-13.md)。

## 已完成調整：Task／Run HPL 編譯預覽 API

- 已部署 `specification/compile-preview`，沿用既有 Task／Run／NamingContract storage 與版本驗證，回傳 HPL 候選及 checksum，不保存產物、不派發執行。
- 62 項本機、4 項真實 PostgreSQL API、部署後 8 項網站回歸通過；2 項 opt-in 測試跳過。網站 ready，ETL 執行仍關閉，CONTROL Worker 已恢復。
- 尚未有對應編輯／預覽 UI，也未完成規格持久化核准及執行接線。[驗證與限制](verification/compile-preview-api-2026-09-13.md)。

## 已完成調整：Hop 原生合成資料列驗證

- CSV bytes 預檢→HPL 編譯→Hop 原生 metadata→LocalPipelineEngine 實際執行已串成可重現開發測試。7 筆來源經 Filter 後 4 筆、聚合為 3 筆，與固定標準答案一致；46 項規格／編譯測試亦通過。
- 測試端在記憶體中用 collector 取代 TableOutput，不更改產品目標，也不宣稱 Vertica／平台 E2E 完成。未接入 API／Worker、不新增模型用量。
- [實際計數、checksum、標準答案與限制](verification/hop-row-probe-2026-09-13.md)。

## 已完成調整：CSV 原始內容預檢

- 新增 bytes 層級結構驗證，檢查編碼／BOM、標題、缺少與額外欄位、引號跨行及掃描上限；回傳 checksum 和統計，不回傳資料值。
- 14 項新測試加 46 項規格／編譯回歸共 60 項通過。尚未接入網站／Worker，未驗證 Hop parser 等價性、型別值及不可變來源執行綁定，不能視為 ETL 成功。
- [驗證與剩餘門檻](verification/csv-content-2026-09-13.md)。

## 已完成調整：規格驅動 HPL 候選編譯

- 已驗證的規格與命名契約可產生確定性 HPL 候選，包含 CSVInput、Filter 真／假路徑、排序、聚合、投影與 TableOutput；不內嵌 credentials 或來源實體路徑。
- 46 項本機測試通過；原生 Hop 載入 7 節點／6 連線，欄位傳播與 Filter／GroupBy metadata 保留檢查通過；四項原生正反例再次通過。
- 候選明示不可執行，CSV bytes／欄位政策、真實資料列語意、持久化核准、connection 綁定及 Vertica QA／Release 均未完成。未接入網站／API／Worker，不新增模型呼叫。
- [證據、重現與限制](verification/hpl-compiler-2026-09-13.md)。

## 已完成調整：Hop 原生 metadata 驗證基礎

- 新增離線原生 `PipelineMeta` 檢查器，四項真實 Apache Hop 2.12 metadata 正反例通過：基本流程、缺少插件、無效連線與拒絕 DOCTYPE。
- 此批僅補上引擎原生載入驗證工具，尚未產生新版規格對應的 HPL、不做資料處理或 Vertica 寫入，亦未接入平台 release gate。
- [重現方式、證據與限制](verification/hop-native-metadata-2026-09-13.md)。模型派發設定未改動，無新增 Copilot 呼叫。

## 已完成調整：EtlSpecificationV1 與唯讀編譯預覽

- 新規格綁定 Run／輸入／設定／最新已確認 NamingContract 的版本與 checksum，明確描述 Filter、分組聚合與輸出投影；任意 SQL、未知欄位、型別縮減及未支援操作會被拒絕。
- 新增 `POST /api/tasks/{task_id}/runs/{run_id}/specification/validate`，讀取既有控制資料後產生確定性計畫，不新增第二套 Task 系統、不保存規格、不派發、不產生 HPL。
- 舊 Hop 產生器含固定前 10 筆與固定計算欄位，新版未直接串接。首個 Filter／Aggregation 編譯計畫已可驗證，原生 HPL／引擎接線仍待下一批。
- 196 項本機、34 項隔離 PostgreSQL／API 與 8 項網站回歸通過。網站首次回歸抓到專案初始載入覆蓋草稿競態，已修正並加入可重現的延遲回應測試。
- 部署檢查另發現 nginx 固定舊 API 位址造成 502，已改為 Docker DNS 定期解析並恢復服務。API 重建／網站不重啟測試通過，但重建時 IP 相同，再次換址情境尚未實測。
- [契約、API、驗證與限制](verification/etl-specification-2026-09-13.md)。P1–P3 尚未達標。

## 已完成調整：CSV 輸入契約與 SA 歷史證據

- CSV 需求檢查新增編碼、分隔符號、標題列、額外欄位政策的明確契約；缺漏先停在 NEEDS_INPUT，不交由模型猜測。
- 需求補正可只修改 CSV 契約並建立新版；舊快照與來源實體資訊不變，新版須重新確認。只有單一且取得方式明確的 CSV 來源可補正。
- 新 SA Context／prompt 為 v2，包含白名單 CSV 語意與來源快照參照，不含實際檔案路徑、機密或資料樣本。已授權紀錄則讀取原 Context，保留先前 v1 內容及 checksum。
- 155 項本機回歸、32 項隔離 PostgreSQL 測試與 7 項網站回歸通過；未追加模型呼叫。模型派發已關閉，本機 Copilot Worker 已停止；CONTROL Worker 仍執行初步檢查。
- [驗收與剩餘限制](verification/csv-input-contract-2026-09-13.md)。這不是 CSV 實際載入、模型複驗或 P1 引擎驗收。

## 已完成調整：Task 六頁籤工作區

- 專案內 Task 改為概覽、需求與規格、協作紀錄、產物與流程、執行與 QA、交付；頁籤使用獨立 hash 網址，支援重新整理、瀏覽器返回與方向鍵操作。
- 保留需求補正與版本確認、完整來源設定、節點細節與事件、Hop XML／連線／SQL、執行 Log、錯誤資訊及既有成功產物下載。補正草稿跨頁籤保留；離開 Task／重載仍沒有草稿保護。
- 協作頁讀取同一套 Run、approval、events 及 SA invocation，沒有另建執行紀錄。真實既有 Copilot 紀錄可查，不追加模型呼叫。
- 未接通的 Developer／QA 交接、SDM／manifest／Release ZIP 清楚顯示限制。移除新主頁面中舊「立即執行」入口，避免誘導繞過新版驗證；舊程式仍保留但主路由不再使用。
- [功能對照、驗證與限制](verification/task-workspace-2026-09-13.md)。

## 已完成調整：常駐 Worker 與服務狀態

- Windows 常駐模式、受控啟停腳本及三種 Worker 的資料庫心跳已完成；Task 與設定中心可查看，不再把設定開關當成在線證據。
- 真實 Windows 觀察程序的正常停止、強制中止後 TTL 離線、重新啟動及網站顯示已通過；全程不呼叫模型。
- 常駐派發模式曾啟動並驗證；CSV 契約升版時已安全停止。當前模型派發關閉，後續真實呼叫需重新取得授權；不重送未知結果。未提供 Windows 開機自啟。
- [本輪測試與剩餘限制](verification/worker-lifecycle-2026-09-13.md)。

## 已完成調整：受控 SA 派發與本機 Copilot

- 新增持久化授權、原子領取、heartbeat、期限及不可重送政策；同一 Run 的授權綁定輸入／設定／Context／prompt/schema 版本。
- UI 可明確授權排隊、讀取狀態與取消尚未領取的工作；啟用開關不等於 Worker 已上線。
- 使用者同意後，已完成一次真實 Copilot CLI / gpt-5.4 的 UI→API→Windows Worker→模型→PostgreSQL→UI 驗收；模型指出 2 個需求問題，回覆 NEEDS_INPUT。未呼叫 Hop／Vertica，未產出 Release。
- Windows Worker 使用 Docker-exec bridge，不複製 GitHub Token、不開新監聽 port；單次模式保留，常駐模式已於後續補上。
- [驗收細節、實際用量與限制](verification/copilot-sa-2026-09-13.md)；[本機操作方式](local-copilot-worker.md)。

## 已完成調整：設定中心分類

- 設定中心改為六分類導覽，保留原有欄位及 API；分類切換不卸載表單，尚未儲存的輸入仍保留。重新整理或離頁的草稿保護尚未完成。
- AI Profile／平台 AI 預設、資料連線、執行路徑、命名政策、驗證策略、機密與部署安全分開呈現；安全限制仍為唯讀。
- 網站建置與部署成功，六項瀏覽器回歸通過，包含分類切換後保留輸入、設定保存重載、專案與歷史 Task 流程。
- 本次未啟用模型或 Hop／Vertica 執行，不能據此宣告 P0 或完整平台驗收完成。

## 已完成的網站基礎（歷次進度）

### 後續進度：專案執行預設選單

- AI Profile 與 Vertica ETL/QA 預設改為選單，可選擇沿用平台；後端明確接受空字串表示繼承，仍保留舊預設值的相容性。
- 顯示本專案或平台來源；未知／停用舊值保留提示，不自動替換。控制 PostgreSQL 不列為 ETL 目標；可選值不代表已連線。
- 可重新讀取選項與前往平台設定中心。搜尋式選單與多連線管理仍待完成；設定分類已於後續補上。
- 11 項專案／設定解析測試通過。瀏覽器首次发现選單名稱混入說明文字，修正可存取名稱後，6 項全套回歸重跑通過，包含選擇平台繼承、保存與重載。
- 後续工作以最上方狀態表為準；歷次測試數不代表完整 P0–P3 驗收。

- 已將首頁改為可搜尋的專案清單，不再自動開啟第一個專案；點選後仍先開專案設定。
- 全域入口為專案工作區、Pilot 成果、平台設定中心、操作指南。
- 舊 dashboard 顯示專案首頁；usage 顯示 Pilot 成果頁並保留用量紀錄；models/database 導向平台設定中心。這是路由解析相容，不強制重寫瀏覽器 URL。
- Pilot 頁目前是階段狀態與限制說明，不是已完成的成果報表；沒有假指標或無效匯出按鈕。
- 既有 Task 詳情、節點、來源補正與 SA 證據面板保持原有路徑；已於後續搬入上述六頁籤。
- 尚未完成：專案待辦聚合、最近活動、專案第三頁籤與全站未儲存提醒。AI/連線選單已補上；仍不宣告完整 P0。

## 本批驗證

網站 TypeScript/Vite 建置通過；6 項瀏覽器流程通過，涵蓋首頁搜尋、進入設定、返回、舊入口、390px 無整頁水平溢出，以及既有專案 CRUD、設定重載、歷史 Task 與版本流程。

設定中心分類這批只部署網站，未修改資料庫結構、未啟用真實模型或 ETL，也未刪除舊元件與歷史資料。前批專案預設選單另有 API 相容性調整。

## 下一批順序

1. P0 待處理摘要、設定測試紀錄與離頁草稿保護；既有預設選單與設定分類已完成第一版。
2. P0 人工核對介面，擴充真實模型執行中的中斷恢復驗收；已完成常駐模式與單次 Copilot，Bedrock 仍待可用憑證。
3. 進入 P1，讓網站與第一條真實 ETL 交付流程同步完成。
