# Hop 結果未知：租約保護

RunQueue.reap_expired 區分外部寫入是否可能已開始：未開始維持 LEASE_EXPIRED；write_started=true 則 HOP_RESULT_UNKNOWN。事件包含 external_write_may_have_occurred 與 automatic_retry_allowed=false。兩者都停 NEEDS_REVIEW，清除失效租約，不自動重跑。

17 項隔離 PostgreSQL queue 回歸通過（2.06 秒），包含模擬寫入標記後租約到期，持久化結果未知、重複回收無作用、不可再次 claim、不可接受舊 Worker 成功、不可另建 active Run。這些只操作控制資料，沒有實際 Hop／Vertica 寫入。

網站新增執行結果待核對警示，指出部分／全部資料可能已寫入，要求保留 Log 並核對目標。1 項合成 API UI 測試通過（4.4 秒），確認警示及不可補正重跑；不是實際 Hop crash E2E。

api／control-worker／web 已部署，執行與模型派發仍關閉。真正 Hop 中斷、資料核對與人工結案／核准新 revision 流程仍未完成。
