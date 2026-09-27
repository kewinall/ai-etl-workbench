# 第 6 階段：案例與成效量測

狀態：實作中，尚未通過 20 案例驗收。第 5 階段見
[已列功能回歸](stage5-current-status.md)。

## 最新進度（2026-09-27）：交付集合與人工量測

正式 API 回讀：目前可交付 20／20，符合原凍結情境證據 19／20。
第 19 案依操作者確認增加來源序號及排序驗證，作為需求延伸通過真實 QA、
隔離重播與 Release；不改寫原凍結答案或冒充首次通過。
詳見 [順序延伸驗收](ordered-source-contract-2026-09-27.md)。

人工量測已完成事件規則、隔離 DB 儲存、競爭與 HTTP 整合測試、計時寫入 UI、
已知斷線／離頁的放棄處理與正式部署；仍不是完整案例工時或跨裝置連續性證明。
操作者已明確延後實際人工基準，保持未量測與改善率不可用。
詳見 [計時驗證進度](pilot-effort-2026-09-27.md)。
可列印報告已部署並逐案唯讀核對，仍有完整列印分頁與本機安全標頭差異待驗證，
詳見 [報告驗證](pilot-report-2026-09-27.md)。
第 6 階段仍未完成，不由交付數推論改善率；第 7 階段持久 Worker、重啟、
完整備份還原及 knowledge-workspace 同步仍待驗收。
既有 migration 053 與最新 migration 055 備份均已完成隔離資料庫還原；
055 副本金鑰與 20 份 ZIP 通過 service-layer 驗證，仍非 HTTP 或完整環境復原，
詳見 [第 7 階段](stage7-current-status.md)。

以下為歷史里程碑，案數代表各段當時狀態，不是最新總數。

### 第十八案：LEFT JOIN 失敗復原與交付（2026-09-27）

recovery-left-join 完成。首次專用新空目標只 rename customer_id，原 HPL
保持不變；真實 Hop exit 1／errors 1，診斷引用加密 Log 第 18／25／45 行，
獨立連線 0 列且欄位 customer_id_missing_fault。核對結案後另建新目標及
revision，原失敗表保留。SA v5／Developer v5 重新核准，修正真實 Hop
EXACT_MULTISET 4／4 MATCH、BOUND_PLATFORM_TARGET，涵蓋一對多與未配對左列。

真實唯讀網站回歸 1 passed（1.7s），診斷、版本關聯、窄版及返回通過。
初次 QA v8 NEEDS_REVIEW 指出雙來源契約缺口（下節）；補齊同執行綁定證據
後 QA v9/context v12 真實複核 PASS，兩次 QA 紀錄均保留，沒有重跑 Hop。
候選包隔離重播 PASS，正式 RELEASE_READY；下載指紋、六個 allowlist 成員
及內容檢查通過。正式交付 18／20，尚缺全列投影及 NULL 分組復原兩案、
完整量測報告、第七階段與 knowledge-workspace 同步。

### 第十八案前置：雙來源 QA 目標契約缺口（2026-09-27）

JOIN 復原案已保存真實缺欄位失敗、新連線 0 列查核、核對結案與新目標
revision；修正 Hop 已 4／4 MATCH。真實 QA v8 回 NEEDS_REVIEW，指出缺少
目標 DDL 契約。程式檢查確認此資訊只供單來源，雙來源交接確有缺口，未核准。

新增 target_contract，核對編譯 DDL 與持久化 target claim 的 Run、規格、
HPL、設定、schema/table 及 DDL 指紋，列出精確欄位、nullable、預設值與約束。
明示不是即時 catalog 證明。context v11／v12、QA prompt v9；已 PASS、
進行中及未知結果舊 context 不自動升級。只對 NEEDS_REVIEW 增補同次執行
證據且原內容完全相同時開放明確複核，不重跑 Hop、不覆寫旧 QA。

完整隔離回歸 1249 passed／46 skipped／1 warning（27.01s），exit 0；
API／Worker 同版建置，無活躍工作時部署。舊第十三案仍 RELEASE_READY。
第十八案複核尚待結果，正式交付仍 17／20；不能以這項修正視為該案已交付。

### 第十七案：日期邊界缺欄位失敗與復原（2026-09-27）

recovery-date-boundaries 完成。SA v5／Developer v4 真實審查後，依凍結案例
只在新建登錄空目標 rename record_id；原 HPL 不變，真實 Hop exit 1／errors 1。
COLUMN_NOT_FOUND 診斷引用加密 Log 第 16／23／43 行，獨立連線確認 0 列與
record_id_missing_fault。修正後 probe 自動完成合法派發收尾，未重跑。
核對結案後另建目標及 revision，原失敗與查核證據均保留。

修訂重新核准 SA／Developer；真實 Hop EXACT_MULTISET 4／4 MATCH，包含
起日且不包含迄日，BOUND_PLATFORM_TARGET。QA v8 PASS、隔離候選包重播
PASS、正式 RELEASE_READY，下載指紋、六個 allowlist 成員及內容檢查通過。
真實唯讀網站回歸 1 passed（1.7s），父子版本、診斷指紋、窄版、返回及無
變更請求通過。正式交付 17／20；仍缺 JOIN／全列投影／NULL 分組三個復原
案例、完整量測報告與維運驗收，knowledge-workspace 尚未同步。

### 復原歷史真實網站回歸（2026-09-27）

新增 recovery-history-readonly.spec.ts，以第十六案既有真實失敗與修正版
執行，不 mock API、不新增案例。1 passed（4.5s）：失敗診斷行號及日誌指紋、
核對結案、父子版本關聯、執行頁歷史選擇、返回、390／768／1440px 均通過；
原事件完全不變、沒有 mutating request 或 page error。這是指定復原路徑的
證據，並非全平台所有操作驗收。修正後 worker 已建置供第十七案使用。

### 第十六案：真實缺欄位失敗與新目標復原（2026-09-27）

recovery-filter-aggregate 經 SA v5／Developer v4 及規格、標準答案核准，在
全新、同專案已登錄空目標 rename category，原 HPL 不變且只執行一次。
Vertica 25.3.0-2 真實 Hop exit 1／errors 1，COLUMN_NOT_FOUND 診斷引用
加密 Log 第 18／25／45 行；獨立連線確認 0 列與改名後欄位，保留原失敗表。
人工代理核對後 CLOSED_WITHOUT_RETRY，另建新目標與 revision，沒有重跑原表。

本次亦發現 probe 收尾使用不在 hop_dispatch.finish allowlist 的碼，導致
Hop 與觀察已保存、CLI 卻回錯且派發仍 CLAIMED。修正為既有合法狀態碼，
測試改為包裝真實 finish 驗證其契約；以原請求與已保存失敗狀態只補收尾，
沒有重寫失敗結果或重跑 ETL。修正完整回歸 1236 passed／46 skipped／
1 warning（26.76s），exit 0；修正版 probe 尚待下一次 worker 建置。

新 revision 重新 SA／Developer 核准，真實 Hop 結果 EXACT_MULTISET 2／2
MATCH（A:40,3；B:45,2），BOUND_PLATFORM_TARGET；QA v8 PASS，候選包隔離
重播 PASS。正式 RELEASE_READY，下載指紋、六個 allowlist 成員及內容檢查
通過。正式交付 16／20；本輪未新增瀏覽器復原頁驗證，仍需後續網站回歸、
其餘四案、量測報告、第七階段與 knowledge-workspace 同步。

### 執行復原入口：單次領取與所有權核對（2026-09-27）

新增 opt-in CLI pilot_recovery_probe（不是一般 API），需明確啟用
WORKBENCH_SYNTHETIC_FAILURE_PROBE=frozen-cohort-missing-column-v1，並提供
Task、Run、目前 dispatch binding。先核對唯一同專案 cohort 登錄；正常建立
新目標後，在 Task／target 鎖內核對登錄 DDL 指紋、同 Task／Run 所有權、空表
及精確欄位，才 rename 第一欄以製造缺欄位；不修改 HPL、不 DROP、不重試。
執行後另開連線記錄列數與欄位，非明確終止結果不宣稱 engine_stopped。

新增檢查共 21 passed；完整隔離 PostgreSQL 回歸 1236 passed／46 skipped／
1 warning（27.66s），exit 0。原生 opt-in 測試跳過不可當成 E2E 通過。
尚未部署或執行本入口；下一步建置 worker，完成第十六案模型／核准流程，
以專用新目標驗證真實失敗、診斷、核准修訂、新目標成功及可攜交付。
正式集合仍 15／20，後續五案與第七階段未完成。

### 執行復原前置：凍結案例範圍檢查（2026-09-27）

新增純函式 pilot_recovery_scope，限定五個既定 EXECUTION_RECOVERY 定義、
CSV 指紋與欄位、ai_sample 新目標命名、APPEND、未寫入且非衍生 Run，以及
當前 dispatch binding。16 項單元測試通過；本機 pytest cache 寫入警告不影響
測試結果。函式不執行 SQL、不授予 ALTER 權限，尚未連接故障執行入口或部署。
後續仍須在鎖定下核對 cohort 綁定、同專案／Task 登錄、全新空表，保存真實
Hop 失敗與新連線查詢結果，再以新目標及 revision 復原。正式通過數仍 15／20。

### 第十五案：NULL 聚合語意攔截與修正交付（2026-09-27）

正式 semantic-null-group 完成。真實 Developer 提案副本將 COUNT_ROWS 改為
COUNT_NON_NULL(category)，validate／compile-preview／save 均拒絕，指出
aggregate 節點、函式及欄位差異；沒有新增規格、HPL 或寫入，重複保存只一筆
拒絕事件。唯讀網站回歸 1 passed（4.1s），歷史差異、窄版面及返回通過。

新 revision 經 SA v5／Developer v4，真實 Hop → Vertica 精確 2／2 MATCH，
包含 NULL 組兩列及 A 組一列，來源 BOUND_PLATFORM_TARGET；QA v8 PASS。
候選包隔離重播 PASS，正式 RELEASE_READY；下載 ZIP 指紋與 API 一致，
六個 allowlist 成員及內容檢查通過。首次 SA 未知引用、植錯與修正歷史保留，
未重跑原目標。正式集合達 15／20，尚缺五個執行失敗復原案例、成效量測、
完整維運驗收及 knowledge-workspace 同步，不代表整體目標完成。

### 第十五案前置：SA 引用限定 Schema（2026-09-27）

首次 SA 真實回傳因 SA_UNKNOWN_EVIDENCE 於 RESULT_PERSISTENCE 被拒絕；
用量保存為 PARTIAL，零工具／零自動重試，未寫入。模型原文沒有保存，
不推測具體錯誤 ID，也不將失敗改為成功。

新增依 captured context.evidence[].id 產生 SA 輸出 Schema 的 enum，涵蓋
頂層與每個 issue 的 evidence_ids；Schema 指紋同時用於授權、保存與 gateway。
SA prompt v5 明示欄位 ref、metric ID、JSON path 不是證據 ID；既有伺服器
未知引用拒絕維持。舊授權／輸出不回寫，重新審查使用新 revision。
完整隔離回歸 1215 passed／46 skipped／1 warning（26.34s），exit 0；API／
Worker 同版建置部署，部署前無待領取／活躍工作。正式集合仍 14／20。

### 第十四案：零列門檻植錯與修正交付（2026-09-27）

正式 semantic-empty-result 完成。將真實 Developer 提案副本的 GT 100 改為
GT 20；validate／compile-preview／save 全部 INVALID，回報 filter 節點與
filters.0.constant.value 的預期 100／實際 20。未產生 HPL、未新增規格、
未寫入；重複保存只有一筆拒絕事件。唯讀網站 1 passed（1.7s），歷史差異、
390／768／1440px 及返回均通過，查看沒有觸發變更。

修訂後重新 SA v4／Developer v4，真實 Hop → Vertica 精確 0／0 MATCH，
來源 BOUND_PLATFORM_TARGET；QA prompt v8 引用執行、結果來源與節點證據後
PASS，並非僅憑零筆判成功。隔離候選包重播 PASS，正式 RELEASE_READY；
下載指紋一致，六個 allowlist 成員且內容檢查通過，原目標沒有重播。
正式集合 14／20；仍缺 NULL 聚合語意一案、執行復原五案及後續量測／維運。

### 第十三案：LEFT／INNER 植錯與修正交付（2026-09-27）

正式 semantic-left-join 完成。在真實 Developer 提案副本將 LEFT 改為
INNER，validate／compile-preview／save 均 INVALID，引用 customer_orders
節點、joins.0.join_type、需求路徑及預期 LEFT／實際 INNER。沒有 HPL、新
規格或寫入；重複保存只一筆拒絕事件。唯讀網站 1 passed（4.1s），可查歷史
差異，390／768／1440px 無水平溢出，返回正常且未發送 mutating request。

另建修訂後 SA v4／Developer v5 重新核准；真實 Hop → Vertica 的精確多重
集合 4／4 MATCH，包含一對多與未配對左列 NULL，來源 BOUND_PLATFORM_TARGET。
雙來源獨立轉換意圖交接及 QA prompt v8 真實 PASS；候選包隔離重播 PASS，
正式 RELEASE_READY，下載 ZIP 指紋與 API 一致，六個 allowlist 成員與內容
檢查通過。未重跑原目標。首次 SA 格式矛盾及其用量、第二版植錯均保留。

正式集合 13／20，仍缺零列／NULL 聚合兩個語意案例及五個執行復原案例；
人工基準、完整成效報告、第七階段與 knowledge-workspace 同步仍未完成。

### 第十三案前置：真實 SA 矛盾格式攔截（2026-09-27）

Join 案首次原生 SA 在 RESULT_PERSISTENCE 被拒絕，安全碼
SA_CANNOT_OVERRIDE_GATE；授權時保存的 deterministic_gate 為 CHECKED 且無
issue，因此依驗證分支可確認模型輸出 READY_FOR_REVIEW 卻帶有未解決 issues。
原始文字未保存，不推測其具體問題內容；本次用量及耗時已成功驗證保存，
零工具、零自動重試、無 ETL 寫入。未知結果不轉成成功。

SA prompt v4 明示 READY 必須 issues=[]、未解決問題必須 NEEDS_INPUT；
說明或已接受限制應放 summary，不得刪除真實問題來取得 READY。驗證器沒有
放寬。隔離完整回歸 1214 passed／46 skipped／1 warning（29.08s），exit 0。
API／Worker 已同版建置部署，部署前無待領取／活躍工作。另建新版重新審查，
正式集合仍 12／20；本段不是第十三案語意植錯或交付通過證據。

### 第十二案：日期迄日語意植錯與修正交付（2026-09-27）

正式 semantic-date-boundaries 已完成。在真實 Developer 提案副本把迄日
LT 改為 LE；validate／compile-preview／save 全部 INVALID，回報獨立意圖
filters.1.operator（filter 節點、預期 LT／實際 LE）及日期範圍契約不符。
未產生 HPL、未新增規格、未寫入；相同保存兩次仍一筆拒絕事件。唯讀網站
驗收 1 passed（1.6s），確認歷史、差異、390／768／1440px 與瀏覽器返回。

另建修正版後，真實 SA／Developer 重新審查；原始來源與凍結答案不變。
Hop → Vertica 精確 4／4 MATCH，BOUND_PLATFORM_TARGET，QA prompt v8 真實
PASS；獨立環境候選包重播 PASS，正式 RELEASE_READY。下載指紋與 API 相符，
ZIP 僅六個 allowlist 成員且內容檢查通過，未重跑原始目標。

本案共五個 revision：前兩版需求缺口、第三版 SA 未知結果、第四版植錯
攔截、第五版修正交付。舊未知結果沒有被改為成功或零成本，原始失敗原因
仍不可由已保存資訊還原。正式集合 12／20：正常五案、需求補正五案、語意
兩案。仍缺語意三案、執行復原五案、成效／人工基準與第七階段可靠部署。

### SA 未知結果診斷 checkpoint（2026-09-27）

第十二案在 SA 階段先後補明原生解析失敗／NULL 行為、唯一目標欄位與合成
Pilot 部分寫入風險界線。一次原生 SA 回報 LOCAL_WORKER_REQUEST_FAILED，
已保存 OUTCOME_UNKNOWN_NEEDS_REVIEW，沒有 ETL 寫入，也未重送該呼叫。
舊橋接層將非 RunConflict 全部遮成通用碼，無法由已保存資訊判定當次根因；
其模型用量不可用，不能回填推算或當作零。

補上 SA allowlist 錯誤碼及 MODEL_CALL／RESULT_CHECK／RESULT_PERSISTENCE
階段。失敗結果的用量只有 provider、模型、Run、context、prompt、schema、
輸出指紋及原生零工具／零自動重試欄位核對後才保存，不保存未通過的模型
文字，不把未知結果變成 READY。網站呈現階段，原本成功／失敗歷史不回寫。

完整隔離 PostgreSQL 回歸 1213 passed／46 skipped／1 warning（30.77s），
exit 0；網站編譯通過。Windows 初次局部測試因 pytest 暫存目錄權限出現一個
setup error，並非斷言失败；包含該測試的上述隔離完整回歸已通過。
部署前無 QUEUED／RUNNING 工作，API／網站／Worker 同版建置，API／網站／
控制 Worker 已部署。部署後歷史語意證據 UI 1 passed（4.6s），第十一案
仍 RELEASE_READY。另建新版 SA 真實 READY_FOR_REVIEW，尚不能據此推定舊錯誤
已定位；第十二案未完成，正式集合仍 11／20。

### 第十一案：篩選語意植錯與修正交付（2026-09-27）

正式 semantic-filter-aggregate 已完成：獨立意圖指定 GE 10，對真實 Developer
提案副本故意改成 GT 10。validate、compile-preview、save 全部 INVALID，
指出 filter／filters.0.operator 與需求路徑、預期 GE／實際 GT；無 HPL、無
新增規格、未寫入。重複保存仍只有一筆 SPECIFICATION_SEMANTIC_REJECTED。
這是測試注入，不是聲稱 Developer 自行產生錯誤。

初始 SA 額外要求明確 APPEND 重播界線，已保留 NEEDS_INPUT，補正專用目標、
單次寫入及結果不明停止核對。植錯後再建立新 revision，重新 SA／Developer，
保留前版拒絕紀錄。新版真實 Hop 的 2／2 結果與凍結答案精確一致，來源證據
BOUND_PLATFORM_TARGET；QA prompt v8 真實 PASS，隔離候選包重播 PASS，正式
RELEASE_READY。下載 ZIP 指紋吻合，僅六個 allowlist 成員，內容檢查通過。
本機 ZIP 內容檢查不取代獨立環境的 portability 證據。

新增唯讀瀏覽器回歸 semantic-evidence-readonly.spec.ts，以環境指定已保存的
Task／Run，沒有模型／資料修改或 mock。實測 1 passed（4.4s）：歷史選擇、
節點差異、390／768／1440px 無水平溢出、瀏覽器返回、零 mutating requests、
歷史事件未變。預設沒有指定證據時 skip，不偽造完成。

正式集合 11／20：五個正常、五個需求補正、一個語意案例。其餘四個語意與
五個執行復原未驗收，成效基準及第七階段仍未完成。未重跑已交付原目標。

### QA 意圖交接與拒絕保存紀錄（2026-09-27）

QA 新 v9／v10 context 引用獨立的已確認意圖，透過執行指紋已核對的編譯
欄位對照驗證；修改門檻、計數、來源或輸出即拒絕。舊 context byte/checksum
保持不變，不允許把新意圖當成舊執行的自動補充。Developer 新意圖 prompt
單／雙來源 v4／v5，強制引用 transformation.conditions；QA prompt v8。

錯誤規格保存留下 SPECIFICATION_SEMANTIC_REJECTED，包含綁定指紋與差異，
相同提交不重複記錄；沒有規格保存或執行授權。網站協作紀錄可讀取差異，
新建 Task 與操作指南補上意圖確認流程。預覽／查閱不寫入拒絕事件。

隔離回歸 1196 passed／46 skipped／1 warning（30.70s），exit 0，網站編譯
通過。部署前實查無 RUNNING／QUEUED Run，無待派發模型；API／網站／Hop
Worker 同版建置，API／網站／控制 Worker 已更新，未重播原目標或模型。
正式集合仍 10／20，接續正式語意植錯五案；新 QA 真實模型與交付驗收未完成。

### 轉換意圖與逐欄位網站 checkpoint（2026-09-27）

新增選用 TransformationContractV1：原始來源限定欄位、Filter 常數、聚合
及輸出順序，透過 Naming Contract 對照規格。共用 validator 拒絕差異並
回報節點及需求／規格路徑，不產生 HPL 或保存規格。revision 與輸入 checksum
綁定，SA／Developer 取得獨立意圖證據；舊版無契約時不回寫並明確顯示限制。

新增網站逐欄位編輯及摘要，無 JSON 編輯需求；實際隔離網站／API／PostgreSQL
保存重讀與舊版保留通過，390px 無水平溢出。初次瀏覽器測試停在欄位標籤，
已加入明確標籤；第二次測試讀取已隨頁面重載釋放的回應 body，改為回讀 API
持久化版本後，最終 1 passed（5.8s）。未呼叫模型或 ETL。

最終完整隔離回歸 1184 passed／46 skipped／1 warning（31.22s），exit 0；
API／網站映像建置通過。原 Pilot 容器未更新，既有第十案仍 RELEASE_READY。
新意圖仍需接通 QA 版本化證據、模型交接及新建 Task 導引，再部署同版 Worker
並進行正式語意五案。正式集合仍為 10／20，整體階段不宣稱完成。
操作及限制見 [轉換意圖](../transformation-intent.md)。

### 語意植錯前置盤點（2026-09-27，尚未驗收）

直接呼叫現行 validate_specification，使用既有測試 fixture 的已確認需求，
將 GT 改為 GE、以及 COUNT_ROWS 改為 COUNT_NON_NULL(category)，兩種設計
仍回覆 VALIDATED_NOT_APPROVED。這是可重現的程式層缺口，不是正式集合
中的真實模型／API 植錯驗收，也不代表已授權執行。

原因：目前日期範圍與 Join 有獨立已確認契約可比較，但一般數值門檻、
聚合函數及輸出語意主要仍靠文字審查；型別合法不等於符合需求。
下一步須提供版本綁定、可供使用者確認的結構化轉換意圖，讓共用 validator
比較設計並回報規格路徑／節點／預期與實際值；不能寫死測試答案或只在
Pilot 測試腳本攔截。新契約需納入 revision、SA／Developer context、網站
確認與負向測試，保留舊版 checksum／已交付成果，再繼續正式語意五案。

### 缺漏 CSV 編碼案正式交付（2026-09-27）

第 10 案原版 Gate 實測 CSV 契約不合法、NEEDS_INPUT，未寫入；目前錯誤
定位整份 CSV 契約而非 encoding 子欄位，不能宣稱精確欄位診斷已完善。
補正 UTF-8 後建立新 revision，重新 Gate、真實 SA／Developer，確認
COUNT_ROWS（包含 NULL 列）、SQL_NULLS 分組、不去重與輸出型別。

標準答案先比對登錄 definition／checksum，再綁定核准規格。單次真實 Hop
MATCH 2／2，NULL 組計數 2、A 組計數 1，缺少與額外均 0，來源受控綁定。
真實 QA PASS、隔離可攜重播 PASS、正式 RELEASE_READY；下载 ZIP 指紋與
六項 allowlist／內容檢查通過。第 9、10 案父版均回讀為已被新 revision
取代，原 NEEDS_INPUT 與 write_started=false 保留。

正式集合累計 10／20 案完成執行與交付核對。其餘語意植錯 5 案、執行失敗
復原 5 案尚未驗收；一般数值門檻／聚合意圖的前置攔截仍須核實並補齊。
成效基準、UI 補充回歸、第 7 階段與 Workspace 同步亦未完成。

### 缺漏日期範圍選擇案正式交付（2026-09-27）

第 9 案原版 Gate 偵測 date_scope 缺漏並停止，未開始寫入。新 revision
明定 ALL、amount > INTEGER 100、EXCLUDE_UNKNOWN 與僅輸出 record_id；
來源與固定標準答案不變。新 Gate、真實 SA／Developer 通過，規格與答案
指紋核對後才授權單次 Hop。實際 MATCH 0／0，缺少與額外均為 0，另存
BOUND_PLATFORM_TARGET 證據；未將預期零列當作執行結果。

真實 QA PASS，獨立資料庫可攜重播 PASS，正式 RELEASE_READY。下載 ZIP
指紋符合 API，六項 allowlist 與內容檢查通過。原目標不重跑。
正式集合累計 9／20 案完成執行與交付核對，仍不代表整體目標完成。

### 缺漏 Join 鍵值案正式交付（2026-09-27）

第 8 案原版 Gate 對無 keys 的契約回覆 NEEDS_INPUT／UNSUPPORTED，未寫入。
現行訊息定位整份 join_contract_v1，尚未細分 keys 缺漏路徑；不宣稱有更精確
診斷。新增 revision 明定左右 customer_id 等值 LEFT JOIN、NEVER_MATCH、
EXPAND、CASE_SENSITIVE_NO_TRIM，保留未配對左列及右值 NULL。
新 Gate、真實 SA／Developer 通過，左右同名欄位命名限定來源，規格與固定
答案 definition／checksum 已核對；來源 bytes 不變。

單次真實 Hop MATCH 4／4，缺少 0／額外 0，來源 BOUND_PLATFORM_TARGET；
真實 QA PASS、隔離可攜驗證 PASS、正式 RELEASE_READY。下載指紋符合 API，
六項 allowlist 及內容檢查通過。回讀父版缺口仍在、write_started=false，
狀態為 SUPERSEDED_BY_REVISION；沒有重跑原目標。
正式集合目前 8／20 案完成執行與交付核對，剩餘 12 案與整體驗收仍待完成。

### 缺漏日期迄日案正式交付（2026-09-27）

第 7 案原版實測 NEEDS_INPUT，指出 end_date_exclusive 缺漏，未開始寫入。
此次回讀後建立子 revision，確認 2026-02-01 不包含、起日 2026-01-01 包含，
補明輸出 BIGINT／NULL、ALL／EXCLUDE_UNKNOWN 與保留重複列。新 Gate 重跑
CHECKED，真實 SA／Developer 通過；核對 GE／LT DATE 常數與直接投影後核准。
標準答案依登錄 definition／checksum 核對，未變更固定資料或答案。

真實 Hop 單次執行 MATCH 4／4，缺少 0／額外 0，來源 BOUND_PLATFORM_TARGET。
單次真實 QA PASS、隔離可攜驗證 PASS，正式 RELEASE_READY；ZIP 指紋符合
API、六項 allowlist 與內容檢查通過。原目標不重跑，原缺口／修訂 lineage 保留。
正式集合目前 7／20 案完成執行與交付核對，其餘 13 案與後續整體驗收仍未完成。

### 缺漏寫入模式案正式交付（2026-09-27）

第 6 案原始 Gate 已實測 NEEDS_INPUT，精確指出 requirements_v1.write_mode
缺少，write_started=false。此次回讀原紀錄後建立子 revision，明確 APPEND，
並補足型別／NULL／metric 命名語意；來源指紋與固定答案不变。新 Gate
CHECKED，SA READY_FOR_REVIEW，Developer 規格核對 GE 10、SUM／COUNT_ROWS
及輸出順序後核准。不是覆寫原版或從中途跳過 Gate。

真實 Hop 單次執行 MATCH 2／2、缺少 0／額外 0，另存 BOUND_PLATFORM_TARGET。
真實 QA PASS、隔離可攜驗證 PASS，正式 RELEASE_READY。下載 ZIP 指紋與
API 相符，六項 allowlist 及內容檢查通過。回讀父版為 SUPERSEDED_BY_REVISION，
原 NEEDS_INPUT 與未寫入狀態均保留，補正 lineage 可追溯。
正式集合目前 6／20 案完成，包含第一個完整缺口補正情境；其餘 14 案及
成效／人工基準／UI 補充回歸／第 7 階段仍未完成。

### NULL 分組案正式交付（2026-09-27）

第 5 案首次 SA 要求補明輸出契約及 nullable 與 COUNT_ROWS 的差別；新 revision
明定 category VARCHAR(32)／row_count BIGINT、DDL 允許 NULL 但計數值非 NULL、
SQL_NULLS 同組、保留重複列計數、空來源無虛構組。樣本與固定答案未變。
命名契約包含 $metric.row_count。真實 SA／Developer 通過，核准規格前核對
COUNT_ROWS、column=null、無篩選／去重、APPEND 與輸出順序。

答案 definition／checksum 與已登錄集合一致。單次真實 Hop 比對預期 2／實際
2 組、缺少 0／額外 0，涵蓋 NULL 組計數 2、A 組計數 1，另存受控來源證據。
單次真實 QA PASS，隔離可攜驗證 PASS，正式 RELEASE_READY。下載指紋符合
交付 API、六項 allowlist 與內容檢查通過；未重跑原目標，初次缺口歷史保留。

正式集合目前 5／20 案完成上述執行與交付核對，僅正常成功類五案。
缺口補正、語意故障攔截、執行失敗復原等 15 案仍待完成；成效、人工基準、
UI 補充回歸及第 7 階段尚未驗收，不以五案替代完整目標。

### 零列案正式交付（2026-09-27）

Worker 已以目前程式重建，沿用 Apache Hop 2.12.0 及相同指紋 JDBC；驅動從
既有 Worker 取回至 Git 排除的本機建置目錄，未另行下載、更換或提交驅動。
舊映像保留 rollback tag；本次僅供複製的未啟動暫存容器已移除。
新 Worker 的 QA format／contract／replay 程式與本機檔案指紋一致。

第 4 案候選包在隔離目標單次可攜驗證 PASS，核准後 RELEASE_READY。
實際下載 ZIP 指紋與交付 API 一致；六項 allowlist 產物及內容檢查通過。
原目標未重跑。前兩次 SA NEEDS_INPUT 與 QA v6 NEEDS_REVIEW 均保留，
不算首次準備成功。正式集合目前 4／20 案完成執行與交付核對；仍待其餘
16 案、量測與人工基準、UI 補充回歸及第 7 階段維運／備份還原。

### 日期格式證據補足與真實 QA 複核（2026-09-27）

新增 source_formats 證據，逐一核對 CSVInput 的欄位 format 與已執行 HPL
checksum；DATE／TIMESTAMP mask 有明確值，並標示不代表全面非法日期拒絕測試。
context 升為單來源 v7／多來源 v8；原版內容可重新建構，舊 PASS、pending、
unknown 不自動遷移。有限複核只能移除新增欄位後精確還原舊 context，不能改
需求、來源、檢查或 HPL；舊 NEEDS_REVIEW 仍保存。QA prompt 升為 v7。

相關 43 測試通過，完整隔離 PostgreSQL 1162 passed／46 skipped／1 warning
（24.92 秒）；第一次全回歸的唯一失敗是舊 prompt v6 固定斷言，已更新並
增加新指引／限制斷言後重跑通過。已部署 API，前三案 RELEASE_READY 與
交付指紋不變。第四案同次執行的真實 QA v7 PASS、issues=[]；v6 NEEDS_REVIEW
未覆寫，沒有重跑 Hop。已核准 QA、保存 SDM 與候選包，尚待可攜驗證／Release。
下一步先核對可攜 Worker 是否相容新增 QA context，不能拿舊 Worker 強行處理。

### 零列案 Hop 通過、QA 阻擋（2026-09-27）

第 4 案第 3 次準備的 Developer 真實提案通過，核對 amount GT INTEGER 100、
EXCLUDE_UNKNOWN、只投影 record_id、APPEND、無聚合。標準答案先與正式登錄
definition／oracle 指紋核對，再核准本版規格與零列答案。
單次真實 Hop 完成，EXACT_MULTISET 預期 0／實際 0、缺少 0／額外 0，
另存 BOUND_PLATFORM_TARGET 證據；未將零筆單獨視為成功。

真實 QA 回覆 NEEDS_REVIEW：需求要求 YYYY-MM-DD，但模型收到的 runtime
options 只有 type／length／precision／trim_type，缺少 date format 綁定證據。
已確認 hpl_compiler 會產生 DATE 的 format=yyyy-MM-dd，而 qa_runtime_options
的 expected／inspect 都未包含 format，屬交接證據缺漏；不能據此跳過 QA。
尚未核准 QA、未產生 Release 候選。不得重跑原目標。
下一步新增版本化、與已執行 HPL checksum 綁定的 format 證據與檢查，保留舊
PASS context／核准，以及此次 NEEDS_REVIEW；回歸後對同次執行作有限複核。
格式設定證據不可誇大成所有非法日期輸入皆嚴格拒絕的 runtime 證明。

### 零列案與 SA 階段邊界修正（2026-09-27）

第 4 案尚未交付。首次 SA 指出輸出契約、重複列規則，以及需求中零筆宣稱
缺乏實測依據；以 revision 補明 BIGINT／nullable、保留重複、EXCLUDE_UNKNOWN，
固定樣本與答案未變。第二次 SA 卻要求需求階段提供尚未產生的 Hop 節點與
結果來源證據，形成階段死結；未核准 Developer，未執行 Hop。

SA prompt 升為 v3，明定 REQUIREMENT_GATE 在設計／編譯／執行之前，後續
證據是強制 downstream 驗收條件，不是當前缺件；仍須攔截真正缺漏、衝突與
不安全操作，不得推定預設或推翻程式 Gate。新增測試確認 prompt／checksum／
版本實際傳入，原始需求未刪除；mock 測試不證明模型語意正確。
局部 17 passed；隔離完整回歸 1151 passed／46 skipped／1 warning（25.50 秒）。
已部署 API。第 3 次 revision 明確分工後，以真實 Copilot SA v3 驗證，
READY_FOR_REVIEW、issues=[]，明確保留後續 Hop／來源證據要求。
兩次舊 NEEDS_INPUT 未覆寫；第四案仍待 Developer、Hop、QA 與 Release。

### LEFT JOIN 案正式交付（2026-09-27）

第 3 案在第 1 次準備完成：真實 SA READY_FOR_REVIEW、Developer 提案保存並
核准。兩來源命名含限定 source 名稱，左右同名 customer_id 不衝突。
核對 LEFT／NEVER_MATCH／EXPAND／CASE_SENSITIVE_NO_TRIM，以及只輸出左鍵
與右 order_code；固定目錄 definition、oracle checksum 先核對後才保存答案。
真實 Hop 單次執行 EXACT_MULTISET MATCH：預期 4／實際 4、缺少 0／額外 0，
包含一對多及未配對左列的 NULL；另有 BOUND_PLATFORM_TARGET 證據。
單次真實 QA PASS、無 issue，隔離可攜驗證 PASS，正式交付 RELEASE_READY。
下載 ZIP 指紋符合 API，六項 allowlist 產物與內容檢查通過，未重跑原目標。

正式集合目前 3／20 案完成上述執行與交付核對；尚餘 17 案、完整量測與
UI 補充回歸及第 7 階段。不可用三個成功交付直接推算整體首次通過率。

### 日期邊界案正式交付（2026-09-27）

第 2 案首次 SA 指出通用「全部期間」文字與指定日期案例易混淆，保存
NEEDS_INPUT，未執行 Hop。修訂版明定 GE 起日／LT 迄日、ALL、EXCLUDE_UNKNOWN、
只映射 record_id BIGINT，未更動固定樣本與標準答案。
新 SA READY_FOR_REVIEW、Developer 提案驗證及命名／規格核准完成。
標準答案先核對既有登錄 definition 與 oracle checksum，再綁定本版規格。
真實 Hop 單次執行 EXACT_MULTISET MATCH：預期 4／實際 4、缺少 0／額外 0，
另存來源 BOUND_PLATFORM_TARGET 證據。單次真實 QA PASS、無 issue。
隔離可攜驗證 PASS，正式核准後 RELEASE_READY；實際下載 ZIP 指紋與 API
相符，六項 allowlist 產物及內容檢查通過。沒有重播原目標。

目前正式集合 2／20 案已完成上述執行與交付核對；兩案都不是首次準備成功。
仍待其餘 18 案、完整成效／人工基準、補充 UI 回歸與第 7 階段驗收。

### 首案正式交付（2026-09-27）

隔離可攜資料庫唯讀預檢成功；候選包在獨立目標僅執行一次，
可攜驗證 PASS。依使用者委託完成指定候選版本核准，狀態 RELEASE_READY。
實際下載 ZIP 的 SHA-256 與交付 API 保存值一致；六個頂層產物為
HPL、HWF、DDL、SDM、參數範例及 manifest，無來源 CSV。
未重跑原始 Hop 目標。首案仍是第 3 次準備才成功，不計首次通過。
以下較早的 PORTABILITY_REQUIRED 敘述保留為歷史，不代表目前狀態。

下一步：其餘 19 案的真實驗證、20 案成效彙整及第 7 階段維運／還原。
knowledge-workspace 同步仍受前次安全審查限制，尚未完成；不以本文件替代同步。

已補安全失敗代碼／階段保存；若已收到且驗證過綁定的 provider trace，保存
用量與 checksum，標記 RECEIVED_NOT_ACCEPTED，不保存失敗模型文字或例外
原文。網站可顯示失敗階段，舊 unknown 紀錄明確顯示未保存、無法追溯。
不回填舊原因，不重播同一 invocation。隔離完整回歸 1150 passed／46 skipped／
1 warning（25.34 秒），build 通過；已部署並以真實 UI 檢視舊紀錄。

另確認首案命名契約缺兩個聚合輸出，依 compiler 規則無法涵蓋規格；尚不能
證明這就是前次 unknown 的原始原因。已建立命名第 2 版及 Run 第 3 次準備，
補入 $metric.total_amount／$metric.row_count；來源、門檻及固定答案不變。
新 SA READY_FOR_REVIEW，Developer 真實提案通過程式驗證，規格第 1 版保存。
已確認單一 amount GE 10、category 分組、SUM／COUNT_ROWS、輸出順序與型別。

規格與從固定目錄核對的答案已核准，既有 Worker 主要執行程式四檔與現行
source SHA-256 一致。單次 Hop 在新受控目標執行完成，Vertica 實測
EXACT_MULTISET MATCH：預期 2／實際 2、缺少 0／額外 0，來源核對為
BOUND_PLATFORM_TARGET。QA 單次真實審查 PASS、issues=[]，已保存核准及
QA-linked SDM。交付候選包已產生，狀態 PORTABILITY_REQUIRED；尚未 Release。
這仍是首案第 3 次準備的結果，不可回算首次成功或宣稱 20 案完成。

下一步先完成此候選包的隔離可攜驗證／正式核准／下載核對；不得再次派發本案
原 Hop 寫入。再處理其餘 19 案與人工基準。第 7 階段維運與備份還原仍未完成。

## 已實作的前置能力

### 最新：正式案例準備與首次嘗試次序

案例準備版本已部署原 Pilot。正式集合 20／20 Task 已固定綁定；真實網站
回讀一致。來源 bytes 唯讀核對符合固定樣本；缺編碼案例如預期呈現
CSV_CONTRACT_INVALID，而不是補入預設值。此結果不代表 20 案已執行通過。

新增 053 migration：已綁定案例的每個新 Run，在相同 Task lock／交易內
分配不可改寫的 attempt_ordinal；重送不增號，取消與修訂都保留。既有無
序號的歷史不回填猜測次序；若存在無序號舊 Run，拒絕為它續編新號碼。
這是「準備嘗試」次序，不把 Gate、模型或 Hop 各自的結果混為首次成功。
隔離 PostgreSQL 1148 passed／46 skipped／1 warning（25.32 秒），build
通過。先新增私人控制 DB 備份，再套用 migration／部署；未更新既有 Run。

正式首案及五個缺口案例已各建立第 1 次 Run、保存輸入核准並由控制 Worker
執行 Gate。五案均為 REQUIREMENT_NEEDS_INPUT，首案初檢 CHECKED；未寫入
Vertica。首案第一次 Copilot gpt-5.4 SA 真實回覆 NEEDS_INPUT：缺目標欄位
型別及來源 NULL 語意。已保存第 2 次 revision，補明欄位型別／映射與
SQL NULL／EXCLUDE_UNKNOWN，不修改樣本或答案。第二次 SA 回覆
READY_FOR_REVIEW、issues=[]；舊結果及 lineage 保留，不算首次通過。
真實網站顯示準備嘗試 #1／#2。兩次 SA 各一個 CLI session、無自動重試或
工具使用；Token 為 PARTIAL，不補零或宣稱已知成本。
命名契約與 SA 交接已確認，Developer 真實呼叫回報 DEVELOPER_OUTCOME_UNKNOWN，
沒有可驗證提案／規格或用量。尚未呼叫 Hop，不可宣稱首案通過。現行 Worker
把例外统一收斂為 unknown，未保存足夠安全錯誤資訊；下一步先修正診斷保存與
未知結果處理，不重播已消耗的 invocation、不改寫歷史。原始原因尚未證明。
人工基準、語意故障、修復及 20 案交付仍未完成。

### 標準案例 Task 準備能力與隔離驗證

新增案例 `prepare` API 與網站按鈕：精確核對已登錄 definition、fixture／oracle
指紋，透過原上傳服務保存固定合成 CSV，核對回傳檔名／大小／checksum／欄位，
採固定宣告型別建立 Task。答案內容不送入 Task／模型；五種結構化缺口保留。
此功能不建立 Run、不呼叫模型、不注入故障、不建立或寫入 Vertica 表。

Task、節點、建立請求鍵與案例綁定使用同一 PostgreSQL 交易；綁定失敗全部
回滾。相同案例重送先回讀既有綁定，不重新上傳或建立 Task。失敗時已上傳的
孤立檔案保留，尚未實作參照感知清除，不能宣稱自動清理完成。

驗證：42 項案例準備／固定樣本測試通過；完整隔離 PostgreSQL 回歸
**1148 passed／46 skipped／1 warning，25.29 秒**，網站 build 通過。初次
回歸發現上傳政策讀取方法不存在，已改用既有 setting 介面後全數通過。
隔離真實 UI 已建立一個標準合成 Task、回讀綁定 1／20、開啟六頁籤 Task
工作區，狀態 CREATED 且無 Run；HTTP 重送 created=false、Task 相同。
這不是正式 20 案驗收；當次隔離驗證時原 Pilot 正式集合仍為 0／20 Task。

後續隔離 UI 已通過返回／重載：再準備一個雙 CSV Join 缺口案例，已綁定
2／20，兩個 Task 仍無 Run；API 讀回兩個來源且 Join keys 為空，沒有預先
補正缺口。隔離驗證不納入正式案例分母。

下一步：先處理 Developer 未知結果，再取得首案 Hop／QA／Release 證據，補情境注入與
缺口修訂、其餘案例。人工基準仍未取得；新按鈕等待中跨頁防護與窄版面尚待補驗。

- 專案範圍的 `POST/GET /api/projects/{id}/pilot-cohorts`。
- 固定 20 案，必須包含成功、需求缺口、語意缺陷、失敗修復四類。
- 每案保存驗收條件、樣本／答案參照與 SHA-256；伺服器不任意抓取參照。
- PostgreSQL 同交易保存全部案例；同計畫重送不重複建立；既有集合不可更新或刪除。
- 登錄不接受 caller 的 passed 值；尚未比對實際資料或綁定 Task，不算執行證據。
- 新版已完成隔離驗證後部署原 Pilot；原 051／052 migration 已套用，案例入口已上線。

## 計算口徑（待接入實測，不能當作已產生的成果）

| 指標 | 口徑及必要證據 |
|---|---|
| 案例符合預期率 | 分母固定為已登錄 20 案；失敗、取消、未執行不得移除。預期攔截與成功交付分別列示，不混稱 ETL 成功率 |
| 首次符合預期率 | 每案第一個完整嘗試；不得挑後續成功 Run 取代首輪。預期缺口被攔截可算情境符合，但不是 Release |
| 修訂／人工介入 | 使用同案例全部 Run lineage 及版本化人工事件；自動工具事件不算人工作業 |
| 缺陷攔截率 | 分母為事前登錄且確實注入的語意缺陷；須有執行前攔截證據與規格／節點引用 |
| 操作時間／經過時間 | 實際人工作業計時與牆鐘時間分列；排隊、等待模型不得混為人工時間；缺值保持 null |
| 成本／Token | 使用各次真實 invocation 用量（含失敗與重試）；缺用量或費率則不可用，不補零；估算须附費率版本 |
| 證據完整率／交付數 | 依情境預先定義必備證據，交付數另核對正式 Release，不用 Task 的舊 status 代替 |

人工比較需相同樣本、標準答案、情境與完成邊界；只具部分人工紀錄時要呈現
覆蓋數，不用完整 20 案的 AI 時間與少數成功人工案例比較。未取得人工基準
之前不發布改善百分比、主管價值結論或虛構工時。此口徑採 KPI 指引的固定
分母、資料來源及防止誤導原則，不另設無證據的改善目標。

## 目前證據與界線

初版登錄包含真實隔離 PostgreSQL 的保存、重送去重、專案隔離及不可覆写
測試；完整控制平面回歸 1094 passed／46 skipped／1 warning。後補的 API
錯誤遮蔽定向測試通過。隔離 HTTP 兩次送出只保存一份 20 案，兩項完成旗標
都為 false。這些是合成控制平面測試，**不是正式 20 案 ETL、模型或人工基準**。
新增 checksum 後的最終驗證結果另記下方，不沿用舊測試假裝涵蓋新欄位。

最終 checksum 版本：24 項定向測試通過；完整隔離回歸 **1100 passed／46
skipped／1 warning，24.66 秒，exit 0**。新版 API 在隔離 HTTP 登錄／重送／
讀回確認一份集合、20 案、樣本指紋一致、execution_verified=false。測試
環境已停止且 volume 保留；未套用 Pilot migration，未呼叫模型或 Hop。

## 下一步

### 原 Pilot 部署與正式案例登錄

已先建立控制資料 PostgreSQL custom-format 備份（759,307 bytes），備份
目錄可讀，複製到本機非 repository 私人備份位置。此為部署前保護，不代表
第 7 階段已完成備份還原演練。主金鑰仍在既有部署機密卷，本輪未搬移或更新。

套用 051／052 共兩個 migration，再更新 API／web，維持原派發開關；未啟動
任何新 Run。部署前後 442 專案、434 Task、257 Run、4 正式 Release 數量
一致；既有正式 ZIP 的下載 SHA-256 未改變。新評估入口可讀，原失敗／取消
Run 仍在歷史清單。未修改或重跑已驗收 ETL。

部署檢查後另建立獨立「正式 Pilot 20 案驗收」專案，沿用已驗收專案的 AI
與 Vertica 預設，不隱含切換模型。由真實網站預覽／確認登錄 standard-v1
20 案；這份不是隔離 UI 測試集合。尚無 Task／Run、綁定 0／20，沒有任何
模型或 ETL 呼叫。正式案例仍須逐案建立、執行、人工基準與結果審核。

### 標準 20 案樣本與預覽

已新增 standard-v1 合成資料目錄與 literal oracle；四情境各 5 案，覆盖
Filter／Aggregation、日期邊界、LEFT JOIN 一對多／未配對、零列、NULL 分組。
修復組改用有列的 projection，避免零列不觸發目標寫入卻誤判故障案例通過。
故障只描述白名單變異，目錄程式不執行 SQL、不建表、不呼叫模型。若缺欄位
被更早攔截，必須記錄真實結果，不當作 Hop 執行失敗。

每案含初始缺口／變異、確認後需求、原始 CSV、固定型別與修正後答案。
獨立 reference 計算核對五種資料結果；ZIP 的 fixture／oracle JSON 是登錄
指紋的精確 bytes。樣本 ZIP 明確不是 Release，也不包含執行成功宣稱。

隔離真實 UI 預覽 20 列、未確認時按鈕停用、確認登錄及重載成功；綁定數仍為
0，不自動建立 Task。下載 HTTP 200，20 案共 40 個指紋全部匹配。完整回歸
1112 passed／46 skipped／1 warning（25.46 秒），build 通過。

本輪 WSL 臨時維持程序結束後服務停止，已實際觀察連線拒絕與容器退出；
恢復既有 Pilot 原容器（未更新映像），health 200。新增 4 小時臨時 WSL
維持程序僅供續驗，非持久維運解法；第 7 階段仍須正式處理。隔離測試環境
驗收後停止、資料卷保留。正式 Pilot 尚未套用 051／052 或新網站。

### 本輪 Task 綁定與畫面進度

新增同專案、前瞻 Task 綁定 API 與 PostgreSQL 保護。使用與 enqueue 相同
Task row lock；已存在 Run 不得事後納入，同 Task 不得重複計入案例；綁定
後不可改選或搬到另一專案。同一綁定重送可回讀，包含已有 Run 後的回應遺失
重試。每案列出全部 Run，未執行的案例仍保留在 20 案分母。

專案 Pilot 評估新增可展開的條件／樣本／答案指紋、明確選擇 Task 與固定
綁定入口。隔離真實 UI 已驗證：保存、重載仍為 1／20、同 Task 第二案例
綁定遭拒；390px 截圖中指紋換行且無橫向溢出。不把綁定當成資料已核對、
執行成功或完整成效比較。

完整隔離回歸 1102 passed／46 skipped／1 warning（25.25 秒），build 通過。
初次測試的同交易 now() 相同導致 Run 排序斷言失敗，已改驗完整保留兩個
Run，不再以 UUID 次序當作首次嘗試證明；首次通過率仍待權威次序設計。
後續補綁定 HTTP 錯誤遮蔽定向測試。只部署隔離環境，Pilot migration
051／052 尚未套用；正式 20 案及人工基準均未完成。

1. 將已登錄標準目錄接到受控 Task 建立／上傳／答案輸入，逐案核對引用的精確內容；正式專案尚無 Task，不可混用 UI 測試專案。
2. 補首次嘗試權威次序；目前已接登錄預覽／下載、案例读取／Task 綁定與全歷史集合。
3. 保存人工量測來源、時間與版本，再接情境判定／成本／可列印報告。
4. 執行正式案例並檢查 UI／API／Hop／Vertica／產物；既有驗收 Run 不重播。
5. 第 6 階段通過後再完成第 7 階段 Worker、備份還原與重啟驗收。

knowledge-workspace 尚未完整同步，既有發布限制仍未解除；此文件不是同步證明。
