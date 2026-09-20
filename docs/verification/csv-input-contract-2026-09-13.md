# CSV 輸入契約與歷史 SA Context 驗收

## 原因與變更

先前唯一真實 Copilot SA 回覆指出 CSV 輸入格式與額外欄位處理不明。原 Context 只傳欄位名稱／型別，需求補正也無法保存這些語意。

本批新增 `CsvInputContractV1`：編碼（UTF-8／UTF-8-SIG／BIG5）、分隔（逗號／分號／Tab／直線）、嚴格 boolean 標題列、額外欄位 REJECT／IGNORE。四項無隱含預設；不接受任意路徑、SQL 或額外欄位。

- 初步 Gate 對 CSV 缺漏契約回傳 NEEDS_INPUT；多來源或舊式不明來源回傳 UNSUPPORTED。
- 單一 CSV 的補正走既有 revisions API，同一交易保存來源契約、新 Run 與舊版取消標記；同請求冪等、不同內容重用 key 回傳衝突。原始檔案與來源私有資訊不改寫。
- 新版本須重新確認，再由控制 Worker 檢查；契約確認不是檔案驗證，也不是 ETL／Release 核准。
- Context v2 傳遞來源 source.0 的快照綁定與白名單 CSV 語意，prompt v2 說明實體路徑刻意排除。已排隊但 prompt／Context 過期的工作仍按既有政策拒絕派發。
- SA context API 如已有 invocation，回傳授權當時捕獲的 Context 並核對 checksum；尚未授權則顯示目前規則的預覽。歷史內容不因程式升版而重算。

## 測試與現場證據

| 驗證 | 結果 |
|---|---|
| 本機選定完整回歸 | 155 passed，4.84 秒；包含 CSV 嚴格驗證、source revision、SA gateway、設定、命名、上傳與原 Hop 產生器 |
| 真實隔離 PostgreSQL／API | 32 passed，4.51 秒；CSV-only 修訂、Tab／false 保留、冪等／衝突、重新確認、原快照與私有來源資訊保留、授權 Context 不重算、既有佇列回歸 |
| 真實網站回歸 | 7 passed，18.9 秒；另外 2 個付費模型／native lifecycle opt-in 案例跳過 |
| CSV 網站流程 | 缺漏契約 → NEEDS_INPUT → 表單四欄補正 → 新版 → 人工確認 → CHECKED／PIPELINE_NOT_READY；資料庫中保存相同契約 |
| 窄版畫面 | 390px 表單無整頁水平溢出；已目視確認。截圖位於 frontend/test-results 的 csv-contract-form.png |
| 原真實 SA 紀錄 | Task TASK-20260913-0018 的 Context 仍為 v1，來源 CAPTURED_AT_AUTHORIZATION，checksum 仍為 07c8a2bbf1e380fbd9b8041610d3b99bc47cae9f020b2d4d8647bb203cd03c5a |

整合測試中的模型結果皆為合成；沒有再呼叫 Copilot 或 Bedrock。

## 部署與限制

網站、API 與初步需求檢查 CONTROL Worker 已部署。恢復持續模型派發被安全審查拒絕，因此目前 `WORKBENCH_SA_DISPATCH_ENABLED=false`，本機 Copilot Worker 保持停止。不得把之前一次真實模型授權延伸為持續呼叫許可。ETL 執行仍關閉。

尚未驗證使用者指定契約與實際檔案內容是否一致；不涵蓋 quoting／換行等完整檔案 parser 契約。新規格到 deterministic compiler／Hop／Vertica 的 P1 接線仍未完成。P2 四案例與 P3 成效量測仍未完成，不能以本批通過宣告整體交付。
