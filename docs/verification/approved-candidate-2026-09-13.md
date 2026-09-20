# 已核准規格候選：內部準備驗證

approved_candidate.load_approved_candidate 在呼叫者交易中沿用 specification_store.context，取得 Task-first lock、Run／Naming，查最新 specification 與其人工 approval。只用資料庫保存的規格編譯，不接收任意 HPL 或核准旗標；重新核對輸入／設定／命名與規格 checksum。

9 項隔離 PostgreSQL 測試通過（1.94 秒）：沒有 approval 阻擋；核准後可產生候選且不改 Run；新增 Naming draft 後拒絕舊核准候選；新增規格後不能取得舊規格候選。包含既有 specification API 回歸。

候選明確 execution_authorized=false；不是可跨交易使用的執行許可。释放鎖之後仍須在 dispatch 交易重新檢查，且 staging／連線／寫入核准／執行證據尚未整合。沒有模型或 Hop／Vertica 呼叫。本次僅建測試映像，既有 API 容器未重建；測試後恢復原 CONTROL worker。
