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
