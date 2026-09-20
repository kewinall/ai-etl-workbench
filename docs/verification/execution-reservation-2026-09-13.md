# 執行授權單次原子領取

migration 031 建立 reservation，authorization_id／run_id 唯一、UPDATE 不可變。內部 reserve 檢查部署開關、Task-first lock、有效授權、未消耗、目前規格核准及準備結果所有 binding；同一交易保存 reservation、Run RUNNING/HOP_PREPARATION/60 秒租約與事件。write_started 仍 false，函式不呼叫 Hop。

19 項 PostgreSQL reservation／authorization／queue 回歸通過（2.85 秒）：執行關閉拒絕；prepared source checksum 變更拒絕；兩個平行請求僅一個 RESERVED_NOT_STARTED，另一個 EXECUTION_AUTHORIZATION_CONSUMED；租約失效後同授權仍不可重用。

測試僅在測試程序設定 execution=true，以合成資料驗證控制交易；沒有啟動 executor、呼叫模型或寫入 Vertica。運行中的 Compose 始終 execution=false／SA dispatch=false，migration 031 與相符服務已部署。

尚未實作公開授權操作、Worker 掃描／派發、外部寫入前的 reservation 強制驗證、準備與真正啟動之間的版本變更處理、過期邊界整合驗收及人工核對。reservation 不代表已執行或成功。

## 追加：寫入前 reservation 強制驗證

begin_external_write 現在檢查 execution 開關、Run 租約與 HOP_PREPARATION、reservation 與 consent、目前規格／命名／設定／來源／HPL 指紋，最終 SQL 同時檢查 lease 及 consent 到期時間。只有一次可設定 write_started；不直接呼叫 executor。

21 項 PostgreSQL 回歸通過（3.36 秒），含錯誤 HPL binding 拒絕、有效 reservation 可設定控制標記、第二次設定拒絕及原有租約失效保護。原 reaper 測試改以隔離 fixture 模擬既有 write_started，不再透過僅有 INPUT_REVIEW 的不完整授權開始寫入。

API／CONTROL worker 已更新，execution=false。沒有真正外部資料寫入；Worker 派發、檔案最後使用點的核對、授權過期邊界及真實 Hop 失敗驗收仍待完成。
