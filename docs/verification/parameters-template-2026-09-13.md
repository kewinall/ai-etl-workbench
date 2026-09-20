# 交付參數範本與整批回歸

已由 delivery compiler 產生固定 parameters.example 候選文字與 SHA-256。唯一參數為空值 SOURCE_CSV，與 HPL/HWF 宣告一致；不填入來源路徑、主機、帳號或密碼。範本明確說明需在目的 Hop 環境另外設定 local 執行設定與 etl_target metadata，Hop 不會自動載入此說明檔。

build_checked_bundle_candidate 現在對 PARAMETERS 也做重新編譯後的位元組比對。替換為含連線值的檔案，即使重算其 checksum 仍拒絕。這不是任意內容的機密掃描，而是只允許固定範本。

網站新增「查看參數範本與環境需求」，呈現範本及指紋；API/web/CONTROL 已部署。Release 入口及執行限制保持不變。

## 本輪驗收

- 參數／編譯／封裝／HTTP Gate 局部測試：26 passed（0.37 秒）。
- 安全後端整批：448 passed、76 skipped（5.42 秒）。排除 legacy test_api.py；DB 與原生 Hop 整合旗標關閉。
- 首次完整網站回歸：25 passed、1 failed、2 skipped（53.6 秒）。舊測試以全區 pre 定位 HPL，新增產物後匹配四個區塊而失敗。修正為精確定位 HPL details，未刪除斷言。
- 重跑完整網站：26 passed、2 skipped（55.3 秒）。兩項 opt-in 的真實 Copilot／本機 Worker lifecycle 測試跳過，沒有額外模型呼叫。
- 真實規格控制流程 Task TASK-20260913-0231、Run 86fd644b-dba6-474b-afee-d9bafee55795、Specification 3bd29ad3-8fe8-4b19-8126-8e5c80d86800。範本文字與指紋逐項核對 API 回傳。
- 真實上傳替換流程 Task TASK-20260913-0233；新 Run 55fea301-27ca-4e52-99a5-afd770889ad5 保留 parent 98bebad3-352e-4fa9-8cd4-45ddb3803a08。

網站套件含序列化單元、合成 API UI 與真實 UI/API/PostgreSQL 控制流程，不能全部稱為外部整合 E2E，也不能與後端數量相加當完成度。

## 限制

SDM Excel 內容與可攜性仍未驗證；固定範本不提供實際資料庫連線。正式 QA、產物保存、核准與 Release ZIP 尚未完成，本次沒有 Hop／Vertica 執行。P0–P3 目標仍未達成。
