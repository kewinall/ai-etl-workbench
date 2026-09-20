# 真實 Worker／Hop／PostgreSQL 失敗路徑

## 實測結果

使用既有 Docker worker target（Python + Java 17 + Hop 2.12），執行 test_hop_worker_integration.py，4 passed，4.01 秒。其中 NATIVE_NO_CONNECTION 是實際 Hop，其餘三例使用合成執行器。

真實案例依序完成：合成來源上傳、規格保存與核准、單次執行授權、來源暫存核對、授權領取、WRITE_STARTED、Hop CLI 啟動、私有 Log 加密寫入 PostgreSQL、完成失敗回報、解密重讀及暫存清理。

測試保留編譯器原本的 TableOutput，不替換成 Dummy；刻意只提供 local metadata，沒有 rdbms 定義，Java 子程序環境也不包含平台資料庫密碼或加密主金鑰。實際錯誤為 target.0 初始化失敗、databaseMeta is null。原先預期 Log 會列出 etl_target，但實際沒有，已根據原生錯誤修正測試斷言。

Run 最後為 NEEDS_REVIEW／HOP_EXECUTION_FAILED，保留 write_started=true 作為保守的執行階段紀錄；這不表示實際寫入 Vertica。相同授權只領取一次，原始 Log 只保存密文。測試 fixture 清除自己建立的控制資料，沒有刪除既有歷史 Task。

## 邊界

不是 Vertica 資料寫入成功驗收，也不是完整第四 Pilot 案例（指定的缺欄位、人工修正及核准重跑尚待實作驗收）。網站派發、連線 metadata、結果比對 QA、SDM、Release 與四／20 案例仍未完成。未新增模型呼叫。

測試結束後 CONTROL Worker 已恢復，/api/ready 為 ready、execution_enabled=false。
