# 正式集合的模型用量覆蓋

2026-09-27：在既有正式案例量測回應與畫面中加入用量覆蓋，不修改歷史模型紀錄、不發出新模型或 ETL 呼叫。

## 修正的統計風險

SA 的耗時可能只保存在 output trace，不能僅加總共用 duration_ms 欄位。Developer 失敗時已驗證的部分回報則保存在 failure_trace。新讀取器依既有持久化契約取值，涵蓋所有正式集合 Run，含失敗、不明及舊 revision；不把 journal 記錄筆數稱為已確認供應商呼叫次數。

每個 provider/model 分開呈現 input/output/total tokens、AI credits、premium requests、trace duration 的已回報合計、回報筆數及缺漏筆數。任何缺漏使完整合計維持 null；真實零值可保留，空集合不推定零消耗。負值、bool、NaN、Infinity 或錯誤型別被拒收。重複 invocation ID 直接拒絕，不重複計算。

SQL 限定 project → cohort → 綁定 Task → 同專案 Run → 該 Run 的 SA/Developer/QA journal；只讀取允許的用量與角色欄位，不讀 prompt、模型文字或連線。API 不新增事件、不執行工具。失敗／不明紀錄的用量仍是失敗證據，不改為已接受結果。

費率、幣別與成本維持 null；credits 與 premium requests 不等同金額、帳單或完整計費。trace 耗時含請求與本機處理，不是人工工時。逐案另提供全部模型紀錄數，避免只展示最新成功版本。

## 驗證

- 隔離 PostgreSQL 全套 1291 passed、46 skipped、1 warning，27.30 秒，exit 0；新增 11 個覆蓋／缺值／失敗／重複與查詢範圍案例。
- 前端 TypeScript/Vite build 通過。部署前 active Run 與 RESERVED 模型紀錄均為 0。
- 真實瀏覽器 1 passed（8.2 秒）：逐案 Release 狀態一致，用量分組與逐案紀錄數相符，缺漏保持 null；版本入口、返回、390/768/1440 寬度無溢出；無寫入請求或頁面錯誤，前後所有檢查 Run 事件相同。
- 獨立唯讀 SQL 與 API 核對一致：95 筆 journal；93 筆有額度及耗時；已回報 AI credits 438.47980、耗時 1452049 ms。這是有回報部分合計，不是完整總用量或費用。缺漏 2 筆，完整合計 null。
- input/output/total tokens 均未回報；不宣稱 token 為 0，也不以回應字數估算。

## 未完成

尚需處理第 19 案列序歧義、情境證據彙整／首次通過率、人工操作計時及人工基準、主管可列印報告與第 7 階段維運／還原驗收。供應商未回報的 token 不能由平台重建為實測值；缺漏須持續揭露。knowledge-workspace 尚未同步。
