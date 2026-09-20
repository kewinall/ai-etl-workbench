# Hop 結果保存與準備檔案驗證

## 已驗證範圍

- 準備檔案核對 source.csv 與 candidate.hpl 的固定位置、一般檔案、SHA-256；拒絕遺失、內容異動及改指其他位置。讀取上限 50 MiB。此核對不能防止本機管理員在核對後修改檔案；真正 adapter 仍須使用唯讀掛載並在啟動前再次核對。
- Hop 結果僅接受固定欄位；不保存任意例外文字、路徑或額外資料。成功必須提供零 exit code、零 errors 與 log checksum。
- complete_hop 必須匹配目前有效租約、HOP_EXECUTION 階段及 write_started，結果一律 NEEDS_REVIEW。成功為 HOP_EXECUTED_QA_REQUIRED，失敗為 HOP_EXECUTION_FAILED，未知為 HOP_RESULT_UNKNOWN；不授予 QA 或 Release 核准。
- 一般 finish 不再允許完成已開始外部寫入的 Run。重複回報、租約過期回報及已消耗授權再領取皆拒絕。

## 證據

- 本機回歸：272 passed、54 skipped，4.90 秒；排除需要部署資料庫的 test_api.py，外部整合 opt-in 關閉。
- 隔離 PostgreSQL：test_execution_reservation_integration.py、test_execution_preparation_integration.py、test_run_queue_integration.py，23 passed，3.85 秒。包含成功、失敗、未知與過期四種交易路徑。
- 後端映像重建後部署 API、CONTROL Worker，API healthy；網站 /api/ready 回傳 ready、execution_enabled=false。模型派發保持 false。

## 不是完整 ETL 驗收

資料庫測試使用合成引擎結果，沒有啟動 Hop 或連線 Vertica；log checksum 為測試資料，不代表真實 log 已保存。實際 Worker adapter、log artifact 登錄、Vertica QA 與 Release 仍未串接完成。新增 complete_hop 尚無生產執行呼叫者，不能將上述測試視為 P1 完成。
