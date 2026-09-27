# Pilot 啟停：目前支援範圍與安全限制

舊 Windows POC `scripts/start.ps1`／`scripts/stop.ps1` 已 fail-closed，呼叫即報錯，
不進行資料建立、程序終止或 runtime 清理。其舊程式保留供歷史查閱，不再執行。
原 Windows DB、Task upload、staging 與歷史證據不可用遞迴清理方式刪除。

目前部署以 `deploy/compose.yml` 與既有 RockyLinux9 Docker 為準，不使用舊
5173 網站／原生舊 worker。正式網站為本機 5183。不要為了停止平台而執行
WSL shutdown、Docker daemon stop 或 remove-orphans，其他專案也在使用它們。

## 停止前必要核對

1. 停止接收新需求／核准，不再手動派發模型或 Hop。
2. 查核實際程序與控制 DB：無 Run lease、無 QUEUED／CLAIMED Hop request、
   無正在執行的模型呼叫；不能只根據 PID 檔或網站顯示判斷。
3. 如有結果不明工作，先確認引擎／資料庫副作用並保存核對證據；不要重跑。
4. 確認 native Copilot worker 狀態。既有 `stop-local-sa-worker.ps1` 是請求
   graceful stop，不表示看到文字就已停止；仍需確認實際程序已結束。
5. 僅停止本平台的 API／control-worker／web，保留 DB／volumes／檔案；
   若需停止 DB，確認平台讀写者已停止。不要對共享環境做全域停止。

## 尚未完成

一鍵安全啟停、持久 WSL holder、崩潰後 owner 身分辨識與排程模式尚未完成。
不能把本頁或舊入口的安全阻擋當作持久服務驗收。Windows 登入自啟或手動
啟動模式仍待操作者決定；目前沒有安裝 Windows 排程或改全域 WSL 設定。
維護時採已驗證的個別操作、先檢查工作再停止，並記錄部署及 readiness 結果。
