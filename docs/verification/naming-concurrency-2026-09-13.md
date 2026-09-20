# 命名版本與規格核准併發保護

檢視 repository 發現：命名保存先取 max(version)+1，但未鎖定 Task；提交後又讀取最新版本作為回應。多個請求同時執行可能競爭相同版本，或回傳其他請求的版本；命名新增也沒有遵循規格審查的 Task-first lock。

修正：保存命名前先取得同一 Task 的 FOR UPDATE lock，於交易內配置版本並回讀本次 contract_id。規格／Run 審查已使用同一 Task lock，現在命名新增也遵循此順序。沒有變更既有歷史資料或 schema。

2026-09-13 驗證：

- 26 項隔離 PostgreSQL 命名／規格／Run 測試通過。
- 兩個平行命名請求取得不同且連續的版本，各自回傳符合該請求的 checksum／內容。
- 持有 Task lock 時，另一路命名保存經 pg_stat_activity 確認 wait_event_type=Lock；尚未新增命名。釋放鎖後保存成功。
- 部署 API 並恢復 CONTROL Worker。首次部署後立即跑瀏覽器測試失敗；重新確認 ready 後真實規格流程通過（4.8 秒），Task TASK-20260913-0089。未把首次失敗算通過，也不將重跑成功當作首次失敗的根因證明。測試新增最多 15 秒 readiness 等待，仍要求 execution_enabled=false。
- 真實測試只建立合成控制資料，結束恢復連線設定並取消 Run；沒有模型呼叫或 Vertica 寫入。

這驗證了正式 repository 保存路徑的 Task 鎖協調，不表示任意直接 SQL 寫入受到相同鎖定，亦不代表下游 execution／QA／release 併發都已完成。P0–P3 仍未達標。
