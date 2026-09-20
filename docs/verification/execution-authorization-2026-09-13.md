# 獨立執行授權基礎

migration 030 建立 task_run_execution_authorization，與 INPUT_REVIEW 及 specification_approval 分開。保存 Operator、Run、specification、完整 binding 指紋、建立／到期時間；每個 Run 最多一筆，UPDATE 由 immutable trigger 拒絕。

內部 offer 重新取得目前已核准候選，綁定規格核准 ID、input／settings／HPL／來源 checksum 及單次／無自動重試政策。authorize 必須 consent is True 且 binding checksum 一致；相同請求不重複建立事件，過期或不同 binding 不覆寫原紀錄。

18 項 PostgreSQL 回歸通過（2.51 秒），涵蓋明確同意、錯誤指紋拒絕、重複請求、不可變更新、保持 Run NEEDS_REVIEW/write_started=false。測試只建立合成控制紀錄並清理自身資料，未對任何真實 Task 授權，沒有模型／Hop／Vertica 呼叫。

migration 030 已套用隔離 Pilot，API／CONTROL worker 更新至相符映像。execution_enabled=false。尚無公開授權 API／UI，無 Worker 消耗、原子派發或真正過期派發驗收；此紀錄本身不是完成的執行系統。
