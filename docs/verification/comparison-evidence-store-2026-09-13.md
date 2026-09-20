# 非正式 QA 比較證據保存

新增 migration 035 task_run_result_comparison（已套用隔離 Compose PostgreSQL），保存 Run、證據 checksum、白名單比較結果與時間。結果由 compare_execution_cursor 產生，沒有接受任意比較結果的公開寫入 API。資料表禁止 UPDATE，對同 Run／checksum 去重。

record_execution_comparison 完成 cursor 消費後，在同一 Task lock 與交易內重讀執行答案／事件／日誌綁定，再保存比較紀錄與時間線事件。綁定改變或 Run 不再符合條件即拒絕，不留下部分證據。原始資料列不進證據 JSON。

所有紀錄目前固定 actual_provenance=NOT_VERIFIED、qa_passed=false、release_ready=false，並由資料表約束；缺少必要欄位或超過 16 KiB 拒絕。MATCH 不是正式 QA 成功。

## 驗證

交易邊界補驗：以已部署程式、隔離 PG 與合成 cursor 測試讀取期間 Run 改為 HOP_RESULT_UNKNOWN，保存前再驗證拒絕，紀錄／事件筆數不增加；另注入時間線事件寫入失敗，確認比較表 INSERT 一併 rollback。僅操作自身 fixture 並恢復，不涉及使用者 Run。結果 3 passed／1 skipped（1.54 秒），CONTROL 已恢復。此輪為新增驗收測試，無生產邏輯變更或額外模型／Vertica 呼叫。

證據契約補強已部署：保存與回讀均驗證版本、EXACT_MULTISET、MATCH/MISMATCH、嚴格整數筆數（0–10000）、缺少／多出筆數平衡、MATCH 與指紋一致性、UUID、Hop 事件及 SHA-256 格式。即使重新計算 checksum，也不能接受矛盾 metadata。本機契約/API 24 passed（0.32 秒），隔離 PG／合成 Worker 加契約 22 passed／1 skipped（1.82 秒）。運行 API／CONTROL 已更新，ETL／模型派發未開啟。沒有真實 Vertica 結果驗收。

最新網站接入：GET comparisons 與 Task「執行與 QA」比對面板已部署，沿用標準答案區的 Run 選擇。顯示預期／實際／缺少／多出筆數、答案／授權／Hop 日誌指紋，MATCH 明示非正式 QA。錯誤重讀清除旧結果。部署後瀏覽器 3 passed（12.1 秒），包含合成 MATCH/MISMATCH 面板、503 重試與 390px，另有真實答案保存回讀及六頁籤／節點／下載回歸。比對面板資料為合成，不計入真實 Vertica 驗收。最新真實答案案例 TASK-20260913-0197。

後續新增 GET /api/tasks/{task_id}/runs/{run_id}/comparisons 唯讀 API，回傳前檢查 evidence 欄位白名單與 canonical checksum；沒有 POST 提交比較結果入口。此新增路由尚未部署，網站面板待接入。本機 Run/API 回歸 10 passed（0.45 秒）；隔離 PostgreSQL + 合成 Worker/cursor/API 8 passed／1 skipped（1.85 秒），包含真實保存結果回讀、跨 Task 404 與錯誤遮罩。CONTROL 已恢復。

- 最新 API 映像建置、migration 035 成功。
- 隔離 PostgreSQL + 合成 Worker/cursor：4 passed、1 skipped，1.90 秒。
- 相同比較去重、不同金額保留兩筆 MATCH/MISMATCH、跨 Task 查閱拒絕、UPDATE 被不可變 trigger 拒絕。
- 恢復舊 CONTROL 時，其 migration 容器因缺少已套用的 035 檔案拒絕啟動（Applied migration files are missing from this version）。已使用新映像重建 migrate／API／CONTROL，遷移成功退出並恢復服務。新內部模組隨映像部署，但沒有 UI 或 HTTP 執行入口，也未自動執行比較。

尚未證明真實 Vertica 查詢來源，未完成 QA 核准、SDM、Release 或 P0–P3 全部案例。沒有新增模型或 Vertica 呼叫，未更動原 Windows DB／業務表。
