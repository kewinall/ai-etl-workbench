# 5197 七階段操作與驗收交接

本次是部分完成。5197 已接通專案限定的真實服務，但三個新案例尚未呼叫模型或執行 Hop，不能宣稱新版七階段全鏈通過。5183 不升級、不重跑既有交付目標。

## 可以確認的案例

專案：http://127.0.0.1:5197/#/projects/346e9419-4b0e-4ba7-ad29-1756ca7da833

| 案例 | Task | 目前操作 | 新目標 |
| --- | --- | --- | --- |
| CSV 篩選聚合 | TASK-20261010-0017 | 第①階段核對來源與準備版本 | ai_sample.ui_accept_csv_20261010 |
| Excel 篩選聚合 | TASK-20261010-0018 | 第①階段核對明細、標題第2列 | ai_sample.ui_accept_excel_20261010 |
| 雙 CSV LEFT JOIN | TASK-20261010-0019 | 第①階段核對左右來源、重複鍵展開、NULL不匹配 | ai_sample.ui_accept_join_20261010 |

目前均停在「確認此版輸入」，尚無案例模型呼叫、資料寫入或正式 Release。初始表單只建立準備版本；確認後控制檢查若指出結構化規則缺漏，使用「前往修正 → 補正需求並建立新版」，填入寫入 APPEND／全部資料、轉換、來源解析契約，再預覽差異及建立新版。不能把初始版本當成完整需求契約。固定答案在 examples/ui-acceptance/expected.json，執行前依核准規格绑定欄位並單獨確認，不能從結果倒推。

## 七階段入口清單

所有「前往……」只導覽；實際提交均在階段內，後端重新驗證版本、權限與既有核准。歷史／原始證據來源只讀；缺前置條件、服務離線、狀態過期時停用操作並显示原因。

| 階段 | 真正操作入口 | 核准或前置條件 | 自動接續與限制 |
| --- | --- | --- | --- |
| ①需求 | 建立準備版本、確認／拒絕輸入、預覽修訂差異、建立新版 | 目前 Task／設定一致；修訂不能沿用舊核准 | 保存後讀回；失敗保留本頁草稿，重載前注意尚未保存輸入 |
| ②審查 | 授權 SA、確認／退回 SA | 輸入確認及控制檢查；SA_COPILOT服務心跳 | Worker只消費已授權 SA_QUEUED |
| ③設計 | 確認命名、授權 Developer、核准／退回規格 | SA通過、本版命名及 Developer服務 | 已授權 DEVELOPER_RESERVED 才呼叫模型 |
| ④執行確認 | 保存／確認標準答案、確認並執行一次 | 規格、固定答案、目標副作用確認、HOP服務 | 有效派發請求才單次啟動；回應不明先讀取 |
| ⑤結果 | 查看節點／比對、异常核對結案 | 原執行證據；失聯不得一般重試 | 等待時5秒只讀、背景暫停；產物接共用刷新 |
| ⑥品質 | 授權QA、人工核准／退回、允許時補證 | 同次執行完整證據、QA服務 | QA_RESERVED才呼叫；修正版使用新目標 |
| ⑦交付 | SDM、候選包、可攜驗證、正式交付核准／下載 | QA及人工核准；候選包绑定；隔離驗證證據 | 可攜驗證只執行本專案候選包，不自动正式交付 |

## 真實舊案例，只讀回歸

- CSV：http://127.0.0.1:5197/?evidence=pilot#/projects/8d423121-2125-422c-830f-2d882e973b4b/tasks/TASK-20260917-0007/delivery/d8abcc97-e5d7-4f83-9d47-b244e03730e7
- Excel：http://127.0.0.1:5197/?evidence=pilot#/projects/7974a406-4f6b-4fa7-801b-7204dbf3b4d7/tasks/TASK-20260928-0001/delivery/df438c72-a408-4eef-8a6e-10f2a8445b02

固定 GET-only bridge 只允許上述 Task，POST為405、其他Task／設定為404；來源失敗回503，不合成證據。七階段切換保留同一Run與 evidence=pilot。實際下載CSV 10,452 bytes、SHA-256 f32b964c8071d37dd854f653320eb4ce41041ae01e92220a026aa27d9bb8da2d；Excel 11,208 bytes、SHA-256 603b9e974338cfe9cd25b13d1a7ef680b7b12bd96ff2ba63992ddcb46eef1c2a。前後Run updated_at與WRITE_STARTED數量不變。這是既有交付證據，不代替新版執行。

## 服務與恢復

必須組合 deploy/compose.stage-guidance.yml 和 deploy/compose.ui-acceptance.yml，並指定上述 UI_ACCEPT_PROJECT_ID；不可單獨套用preview設定。控制領取限定Project；Windows scripts/start-ui-acceptance-worker.ps1 隱藏啟動並防重複。其 runtime-temp/ui-accept-attempts intent標記不能為了重試而刪除；可能失聯先核對伺服器結果。建立 runtime-temp/ui-accept-worker.stop 可停止新工作消費，現有執行須先核對結案。停止新環境服務時限定 ai-etl-stage-guidance-ui 專案，不刪volumes、不操作5183。

5197獨立PostgreSQL、來源、產物及加密保管庫；使用者明確授權的一次原連線秘密移轉已完成，沒有明文檔案或Git秘密。原寫入仍僅新 ui_accept_*；UiAcceptPortable 是獨立可攜驗證Vertica DB。心跳代表消費者在线，不代表模型、Hop或資料庫健康驗收。

## 已驗證與未完成

前端build通過；隔離PostgreSQL工程回歸2024 passed／139 skipped／1 warning（46.32s）；新版瀏覽器16 passed／2 skipped（26.4s）。兩個跳過是會建立合成資料的preview專用測試，真實驗收環境不執行。包含既有CSV／Excel真實GET與ZIP回歸；390／768／1440px、鍵盤、版本／返回、草稿、回應遺失／不重送、離線及Join修訂屬隔離UI分支證據，不能擴大為Native分支验收。

仍未完成：三個新案例全部模型／Hop／獨立目標查詢／QA／可攜驗證／ZIP全鏈；真實退回補證、修正版、失敗失聯分支逐項驗收；部分進階元件仍保留人工核對入口，主要接續已接共用讀回，但全面文案收斂仍需逐階段操作確認。JSON／資料表來源仍未完整驗收。

下一步：使用者先在第①階段核對上述三案例，再經網站原有核准接續。每個核准點保存API、持久資料、模型用量、Hop日誌與節點計數、獨立查詢、QA及ZIP指紋；每階段驗證後更新WS-0007，不以畫面或服務啟動判定完成。

## 接續：Join 實際退回與修訂

使用者在網站核准 TASK-20261010-0019 第①版輸入後，控制檢查實際退回 requirements_v1.write_mode／date_scope 缺漏。已由正常網站補正 APPEND／ALL、四欄輸出投影，預覽差異並建立第②版 714fad5b-b564-40bd-a60d-cb61134656a0；保留第①版核准、Join及來源契約，第②版沒有核准或執行。下一步是核對新版差異並重新確認輸入，不沿用原核准。CSV／Excel仍停在原第①版未核准。

問題定位已補上寫入模式、資料期間及鍵欄位的精確焦點，避免把所有缺漏帶到需求文字。真實修訂證據：ui-accept-join-revision-2026-10-10.json；全鏈尚未通過。

## 接續：真實 SA 與失效版本恢復

Join 第②版由使用者確認輸入並保存 SA 授權後，發現專案Task清單不含 latest_run，驗收消費者因此跳過工作。已改為明確 GET Task runs 並選最新Run，限定原有 SA_QUEUED 意圖；防重送標記完整保留。真實 LOCAL_COPILOT copilot/gpt-5.4 執行19,344ms，1次session／premium request、4.26465 AI credits、0自動重試／工具執行；token統計僅PARTIAL，不填假數字。SA READY_FOR_REVIEW、無問題，但 VALIDATED_NOT_APPROVED；下一步是人工確認需求審查結果，未授權 Developer／Hop。證據 ui-accept-native-sa-2026-10-10.json。

CSV／Excel的原準備版本 input相同，但 credential_versions 已變更而失效，沒有核准／写入。修正唯讀保護中取消與建立新快照的資格判定，經正常網站保留並取消舊版、建立新版本：CSV 71c7b365-7770-4de4-b2f0-70c0ad28adf6；Excel 7bf591fd-7409-4d1a-89ba-f852c0555c3d。新版本matches_current=true、等待輸入確認；不沿用舊核准，也未呼叫這兩案例模型。歷史／原始證據來源／過期狀態仍不得取消或建立新版本。證據 ui-accept-fresh-inputs-2026-10-10.json。

Worker真實Task清單形狀回歸3 passed（0.14s）；前端build PASS。全鏈仍未通過，仍需后續命名／設計、固定答案、原寫入、QA、隔離候選包及交付核准。

## 接續：設計階段命名預覽

使用者已確認 SA 結果，Join 進入第③階段；目前未有命名契約，所以 Developer 尚未派發。新增相容唯讀 GET naming-contract/suggestion，沿用 deterministic naming_suggestions，不呼叫模型、不建立契約或核准；設計頁初次直接显示未確認建議，人工核對後才可保存命名，再另行授權 Developer。修改中的建議由草稿離開保護及共用刷新守衛保留，預覽不能算命名通過。Developer API/畫面明示缺命名、SA未確認或上游失效等原因；不暴露原始例外。

真實四欄預覽：source.0.id → id BIGINT、source.0.left_value → left_value VARCHAR(32)、source.1.id → id_2 BIGINT、source.1.right_value → right_value VARCHAR(32)。建議人工將左右id改為left_id／right_id，保留技術來源識別，便於固定答案绑定。若使用id／id_2亦須依核准命名绑定固定答案，不能只為符合結果而改答案。

backend設計契約／Gateway／阻擋原因18 PASS（0.70s），browser23 PASS／1 preview-only skipped（35.3s），build PASS；實際5197頁面4欄預覽、未確認、API寫入0；Run updated_at／命名契約／Developer invocation／write_started未變。證據 ui-accept-design-preview-2026-10-10.json。必要人工點：核對並保存命名，再授權 Developer 一次模型呼叫；仍未執行ETL或完整交付。

## 2026-10-10：Join 真實執行後的按鈕與比對失敗修正

實際進度：使用者已完成命名、Developer、規格、標準答案與 Hop 核准；Run 714fad5b-b564-40bd-a60d-cb61134656a0 的 Hop 成功，Vertica 新目標 ai_sample.ui_accept_join_20261010 有 5 筆，WRITE_STARTED 只有 1 次。獨立唯讀查詢與本次執行前已保存 examples/ui-acceptance/expected.json 的固定答案一致，但不可取代平台 QA 比對。

已核准的標準答案 ce17a841-ba47-4467-ba41-8ecb8fcaad02 實際是 rows=[]、四欄 nullable=false。結果讀取因此為 RESULT_NULL_NOT_ALLOWED；使用者已授權的重新比對 d4113c01-f15b-4ead-bea6-201d938f8f37 已由專用唯讀 Worker 消費一次並記錄 FAILED，沒有重跑 Hop。不得事後改寫已執行版答案、核准或宣稱 MATCH/QA PASS。

修正內容：比對恢復共用讀取更新及唯讀保護；補接 supervisor 比對 consumer，專用 CLI 不會落回 Hop 派發；workflow 留在第⑤階段並顯示具體比對問題；第⑥階段可前往結果區。空白標準答案須明確確認預期零筆。失敗原因只保存白名單代碼，不保存驅動程式原始錯誤或秘密。補接比對 FAILED 後的人工結案與新目標修正版，所有上游核准仍重新確認。

下一步人工操作：開啟 Join 的 results/714fad5b-b564-40bd-a60d-cb61134656a0；在「只重新比對結果」下核對失敗原因與「人工核對與結案」。確認本次 Hop 已停止、核對目標 5 筆，選取 docs/verification/ui-accept-join-comparison-failure-2026-10-10.json 作為本機查核證據，逐項確認後保存結案（不重跑）。再由需求階段建立新目標 ui_accept_join_20261010_r3 的修正版；新執行前明確輸入固定 5 筆答案，id、id_2、right_value 允許 NULL，left_value 不允許 NULL。不能重用原目標或反推答案。平台不會替使用者簽署人工查核或核准。

驗證：完整隔離後端 2035 PASS、139 明示跳過（47.35s）；受影響結案／修正版／比對測試 55 PASS（11.68s）；browser 25 PASS、1 真實執行環境禁用的合成準備測試跳過（34.9s）。實際新 Join 7 階段 × 390/768/1440 共 21 檢視，版本一致、無溢出、無 pageerror、無寫入，QA 返回結果按鈕可操作，人工結案未確認時停用。原正式 CSV/Excel GET-only 下載及指紋回歸通過。

證據：ui-accept-join-comparison-failure-2026-10-10.json、ui-accept-join-buttons-2026-10-10.json。CSV/Excel 仍待人工確認，Join 尚未通過平台比對、QA、可攜驗證與正式 Release，三案例全鏈仍部分完成。5183 未升級；未推送 project source。

補充實際按鈕驗證：依實際 DOM 名稱點選 14 個「重新載入／讀取／核對」按鈕並等待讀回，零寫入、零 pageerror。頁面剛載入時部分按鈕因讀取中暫時停用，不將該瞬間狀態當成永久失效；主要比對恢復問題已以上述保存狀態與服務消費證據驗證。


## 2026-10-10：依使用者要求移除人工核對檔案與重複確認

此更新取代前述「選取查核證據檔案」的操作指引。網站不再提供或要求證據檔案、檔案指紋及三個獨立勾選；改為目標筆數＋一次明確確認＋「確認結案，保留結果」。準備失聯仍需選擇目標是否存在；不存在不能填成零筆。

Join 本次操作：重新整理結果頁，在「結束此次執行，保留結果」填 5；確認本次執行已停止、目標核對正確並同意結案，按「確認結案，保留結果」。結案後前往需求，用新目標 ui_accept_join_20261010_r3 建立修正版。這不會重跑或更改原結果。

API evidence_sha256 改為可省略；migration059 僅移除兩種結案紀錄的檔案指紋 NOT NULL，保留原不可變紀錄及既有指紋，不產生假檔案或假指紋。仍驗證版本、資格、筆數與明確確認，並保存操作人與時間。輸入變更取消确认、雙擊只送一次、回應不明須先讀回。

build PASS；隔離後端2036 PASS/139明示skip/1warning（48.50s），browser27 PASS/1skip（35.5s），包含無檔案結案、準備結案、雙擊與重載；實際5197 Join表單390/768/1440驗證一個checkbox、零file input，填5與確認後可提交，零寫入/零pageerror。證據 ui-accept-simple-reconciliation-2026-10-10.json。驗證沒有替使用者送出此Join人工結案；原Hop寫入1次，QA/Release仍未通過。


## 2026-10-10：結案不再視為退回第一階段

使用者已人工結案此 Join Run，原版本 state=FAILED、outcome=HOP_EXECUTED_QA_REQUIRED、write_started=true，並非 QA 核准或交付。原 UI 把 failed_revision_available 直接投影為 requirements，造成看似重新開始。改為 current_stage=results，顯示「此版已結案；可建立修正版」。明確按「建立修正版（保留此版結果）」才導航開啟沿用原需求的補正表單並定位目標欄位，不呼叫 POST；新版建立後才走需求確認。專案繼續處理使用 current_stage，會先回原結果。

實際人工結案保存 observed_row_count=1；這是使用者聲明，與前輪獨立查得5筆分別保存，不覆寫或將聲明當作再次查詢結果。本次只修改導引，沒有重查/重跑 ETL、改答案或新增核准。下一步新目標 ui_accept_join_20261010_r3 並使用原執行前固定5筆標準答案。

驗證：後端 workflow19 PASS（0.72s）；既有 browser27 PASS/1skip，新增結案導引測試修正測試 selector 後單獨1 PASS（1.2s）；實際已結案 Join 顯示第5階段與結案紀錄，點明確修正版入口沿用原目標與需求、零寫入/零pageerror。部署 web/api build PASS。證據 ui-accept-closed-run-guidance-2026-10-10.json。原Run尚無新版，QA/Release仍未通過。

## 2026-10-10：交付文件自動讀取與缺漏原因

實際 GET 核查此 Join Run 的 sdm-candidates.items=[]；release_ready=false，正式候選包、可攜驗證、交付核准及 Release 均不存在。人工結案僅保留執行結果，不代表 QA 核准，因此本版沒有 SDM 或 ZIP，不能以合成文件替代。

修正交付文件清單進頁自動讀取，接入共用刷新並防止切換版本後舊回應覆寫；已存在的候選文件立即顯示。已結案版本的交付頁顯示「此版尚無交付文件」、比對失敗與 QA 前置條件，以及返回結果入口。仍由既有後端判定產生文件資格。

驗證：部署 web build（含 TypeScript）PASS；browser 30 PASS/1 不適用情境 skip（36.6s），包括自動顯示既有候選與結案空清單。實際 Join GET-only UI 證據 ui-accept-delivery-empty-2026-10-10.json：自動讀取清單、原因可見、結果入口可操作、SDM 建立停用、零寫入/零 pageerror。既有正式 CSV/Excel 唯讀下載回歸包含於上述測試。

下一步：由原結果的明確修正版入口建立新目標 ui_accept_join_20261010_r3，保留原版與原寫入；執行前輸入已固定的 5 筆答案與正確 NULL 契約，重新走必要人工核准。QA 通過後才建立 SDM、候選包、隔離驗證及正式交付。CSV/Excel 仍待人工確認；三案例全鏈仍部分完成，5183 未升級，project source 未推送。

## 2026-10-10：依明確授權完成三案例正式交付

使用者目標「三個 task 案例自動完成測試、執行、驗證、交付」，並直接確認「授權三案例全部自動核准、執行與交付」。代行操作全數使用原網站核准控制與後端資格檢查，並未關閉驗證或寫入資料庫偽造核准。自動安全審查曾拒絕先前目標訊息作為授權，取得上述直接確認後才繼續。

- CSV TASK-20261010-0017：Run5443ccf1-3386-48ba-b669-8c2dbaecd155，ai_sample.ui_accept_csv_20261010，真實 Hop 7 節點、固定答案 EXACT_MULTISET MATCH2/2、獨立 SELECT2筆、QA PASS、隔離 HWF PASS、正式 Release7186c499-7710-4911-aadf-7cf55060c30e。
- Excel TASK-20261010-0018：Run029d55b5-d677-427d-a6c2-7a14511b4de4，ai_sample.ui_accept_excel_20261010，明細第2列標頭、全空白列SKIP、缺值NULL；7節點、MATCH2/2、獨立 SELECT2筆、QA PASS、隔離 HWF PASS、正式 Release27a59421-db00-4d5d-8a4d-d80c2488347a。
- Join TASK-20261010-0019：Rune0b16950-27db-4847-add5-1ddbeaf78e08，ai_sample.ui_accept_join_20261010_r5，LEFT/NEVER_MATCH/EXPAND、9節點、MATCH5/5、獨立 SELECT5筆、QA PASS、隔離 HWF PASS、正式 Release0e5dae86-c2a6-449e-8062-1018ca681a8d。

Join過程保留兩個新的退回：8d93f257的SA NEEDS_INPUT要求目標mapping及NULL解析；5bedf37f的QA FAIL指出本次補充文字NOT NULL與編譯器nullable DDL不一致。NOT NULL是本次補充時不當加入的額外限制，修正為原案例允許NULL的目標契約，保留固定五筆答案，其中left_value實際答案均非NULL；沒有改寫前次需求、答案、QA或已寫入目標。新版使用r5新目標，所有必要核准重新確認；原714fad5b結案版與r3執行/FAIL仍保存。

三案每個最終Run的WRITE_STARTED均1次，不是整個Join Task從未有過其他版本寫入。原始目標與隔離驗證目的地分開；隔離目的地也重新唯讀查詢2/2/5筆MATCH，保存的完整HWF/node日誌與receipt指紋一致。每個最終版SA/Developer/QA均LOCAL_COPILOT、copilot/gpt-5.4、單CLI session、零自動retry、零工具執行；token缺值仍不可用，不以零代替。

正式下載CSV10417bytes SHA25661eb59a6d0e58f5aa5a07b40ddd17eb697e64cdc4e064d29aa7ad1c3a0908e04；Excel11152bytes SHA256e8e38dde9f31cbe0926eeef70a1b090a9e01ff2df4dca8719a9c005e13b063aa；Join10585bytes SHA2569ba3bfdc8caebf5e589547268791e3abc5b701da4a5446a22cc376038854fd35。每包HPL/HWF/DDL/SDM/parameters五產物全數通過manifest size/SHA及ZIP CRC核對；SDM可讀。ZIP与獨立SDM保存於outputs/ui-acceptance-2026-10-10/，不納入Git。

驗證：原介面／固定5183正式CSV/Excel唯讀回歸30PASS/1不適用skip（37.7s），原下載指紋及寫入事件數/更新時間不變。新增真實三案七階段×三寬度共63檢視與鍵盤ZIP下載、重載版本/SDM清單：9案例檢查加1啟用設定測試，10PASS（20.5s），零寫入/零pageerror。工程取證腳本僅GET/SELECT/讀不可變日誌，不會呼叫Hop、改答案或重新核准。

證據：ui-accept-auto-preparation-2026-10-10.json（初始修正版未核准快照）、ui-accept-auto-qa-return-readback-2026-10-10.json（r3執行結果，不代表QA通過）、ui-accept-auto-native-readback-2026-10-10.json（最終原寫入）、ui-accept-auto-portability-2026-10-10.json（隔離執行與独立讀取）、ui-accept-auto-delivery-2026-10-10.json（模型、Release、ZIP/manifest）、更新的ui-acceptance-cases-2026-10-10.json（網站入口）。

三個指定合成案例全鏈已通過；不能推論所有v2分支、JSON/資料表來源或整個v2專案完成。5183未升級；project source未推送。使用者下一步可直接在三案delivery頁查看SDM與下載正式ZIP，不需要手動核對證據檔案或再次執行。
