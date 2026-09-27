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

## 安全停止既有服務

執行 `pwsh -File scripts/stop-pilot.ps1 -CheckOnly` 進行唯讀預檢。
需能查詢 Windows 程序、WSL 與 Docker；任何查詢失敗均拒絕停止。
工具要求原生模型/Hop Worker 不存在，也拒絕同 Compose project 下運行的
非核心容器。不得為了通過檢查而修改標籤或只刪 PID 檔。

`pwsh -File scripts/stop-pilot.ps1` 核對後，依序正常停止 control-worker、
web、api，使用無限 graceful wait，不設定到期 SIGKILL，不刪除任何檔案或
volume，不停止 PostgreSQL。若程序一直在處理請求，命令可能持續等待；
查明真實處理狀態，不另外啟動第二次停止或強制 kill。

預檢與停止後均查核 Run lease／queued/running Run、queued/claimed Hop、
保留中模型呼叫及執行中 portability check。停止後若發現新待處理工作，
回報失敗並保留停止現況，交由操作者檢查，不取消、清除或重跑工作。
結果不明的既有歷史仍保留，不代表那些失敗已解決。

這不是持久的 admission lock：維護期間不得從其他终端啟動 Worker 或直接
連線 DB 寫入。CheckOnly 只表示當下預檢，不代表後續工作不會改變。
本工具不提供一致性備份認證，也不停止共享 Docker／WSL。
恢復核心服務使用下面的 start-pilot；control-worker 不會自動啟動，應確認
需恢復既有控制工作後，手動啟動同一個容器，不啟用新的 execution profile。

## 手動恢復既有核心服務

在專案根目錄執行 `pwsh -File scripts/start-pilot.ps1 -CheckOnly`，唯讀核對
三個正式容器名稱、Compose project/service 標籤與狀態。缺少容器、身分不符、
paused/restarting/dead 等狀態均停止，且先完成全部核對才允許任何 start。

確認後執行 `pwsh -File scripts/start-pilot.ps1`，僅對未運行的既有
postgres/api/web 呼叫 Docker start，最後檢查網站 `/api/ready`。
已運行容器不重啟；不建立容器、不執行 init/migration、不更改派發開關，
不啟動 control/model/Hop Worker。這是恢復既有安裝，不是首次部署工具；
資料庫版本或映像不符應走有備份的部署流程，不自動修補。

此工具未提供 WSL holder，因此不保證 WSL／Windows 重啟後持續服務。
也不代表整套 Worker 已運行。readiness 失敗時保留現況供診斷，不做自動回滾。

## 尚未完成

完整安全啟停、持久 WSL holder、崩潰後 owner 身分辨識與排程模式尚未完成。
不能把本頁或舊入口的安全阻擋當作持久服務驗收。Windows 登入自啟或手動
啟動模式仍待操作者決定；目前沒有安裝 Windows 排程或改全域 WSL 設定。
維護時採已驗證的個別操作、先檢查工作再停止，並記錄部署及 readiness 結果。
