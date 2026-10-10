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
