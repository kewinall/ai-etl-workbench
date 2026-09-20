# 執行答案與有界結果讀取

新增內部 result_reader 及 compare_execution_cursor。使用當次不可變授權選定答案，依其欄位順序檢查 DB-API cursor metadata；每次最多取 100 筆，最多 10,000 筆、canonical 內容 8 MiB。逐批檢查型別及容量，讀取到空批次才完成；錯誤不回傳部分成功。

數值維持 Decimal／int，不經 float 或字串猜型別。比對回應不含原始結果列；即使 MATCH，actual_provenance=NOT_VERIFIED、qa_passed=false、release_ready=false。此函式不建立或執行 SQL，cursor 的查詢來源、交易及清理由未完成的可信目標 adapter 負責。

## 驗證

- 讀取／比對本機套件：40 passed，0.10 秒。
- 隔離 PostgreSQL 控制資料 + 合成 Worker／cursor：4 passed、1 skipped，1.94 秒。完成 Run 使用正確答案 MATCH；相同筆數但金額不同為 MISMATCH；未取得 QA 或 Release 通過。
- CONTROL Worker 已恢復；新增內部程式尚未部署或提供 UI／HTTP 執行入口。

限制：fetchmany 的筆數／內容檢查不代表 driver 本身沒有提前緩衝整份結果，亦不提供資料庫 query timeout。仍需可信 Vertica query、server-side cursor／timeout、執行目標版本與資料範圍綁定、持久 QA 證據、SDM、Release 及完整案例验收。沒有追加模型或 Vertica 呼叫。
