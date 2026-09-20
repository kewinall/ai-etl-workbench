# 本機 Copilot SA 操作

適用本機單一 Operator Pilot。保留 Docker 的控制資料庫及 API；Copilot 在 Windows 使用既有登入，不把登入 Token 存入平台。

## 操作步驟

1. Windows 已安裝並登入 `copilot`；`copilot --version` 只驗證安裝，不能證明帳號可呼叫模型。
2. 平台 AI Profile 選擇「本機 GitHub Copilot CLI」，填明確模型名稱（例如已於本機單次驗收的 `gpt-5.4`），Region/Endpoint 留白，不填 Token。不要使用 auto。
3. 專案選擇此 Profile，建立 Task，確認輸入，等待初步需求檢查。設定存檔不代表 Hop/Vertica 或模型測試通過。
4. 啟用授權入口（不會自行呼叫模型）：

```powershell
wsl -d RockyLinux9 -u root -- sh -lc 'cd /mnt/d/ChatGPT/ai_agents_v2 && WORKBENCH_SA_DISPATCH_ENABLED=true docker compose -f deploy/compose.yml --profile pilot-control up -d api web control-worker'
```

5. Task 的「SA 呼叫狀態」確認單次 Copilot 額度政策後，選「授權並排入 SA 工作」。
6. Windows 啟動常駐 Worker。以下明確開啟派發模式；只有已逐筆授權的 Copilot 工作會被領取：

```powershell
Set-Location D:\ChatGPT\ai_agents_v2
.\scripts\start-local-sa-worker.ps1 -EnableModelDispatch
```

省略 `-EnableModelDispatch` 時是觀察模式，不領取或呼叫模型。腳本隱藏啟動視窗，並拒絕重複啟動。確認「平台設定中心 → 執行環境與路徑」或 Task 的 Worker 狀態顯示「近期有心跳・派發模式」，不能只依賴啟動訊息。

7. 安全停止：

```powershell
.\scripts\stop-local-sa-worker.ps1
```

停止要求不強殺模型；若已有呼叫，等待它完成並保存結果後停止。腳本會核對程序命令與受控 runtime 路徑；若仍在完成工作，必須核對實際程序及心跳後才重新啟動。

保留指定版本的單次模式，可供受控驗收；不要在常駐 Worker 執行時並行執行此命令：

```powershell
Set-Location D:\ChatGPT\ai_agents_v2\backend
..\.venv\Scripts\python.exe -m app.local_sa_worker --task-id <Task編號> --run-id <Run_UUID>
```

Worker 透過固定 `RockyLinux9` WSL 發行版與 `ai-etl-workbench-api-1` 容器 bridge 操作；不同部署須調整 transport 設定。它不開放網路服務，也不將 PostgreSQL 密碼複製到 Windows。

本機程序啟動後常駐，但尚未註冊 Windows Service 或開機自動啟動；重開電腦需重新執行啟動腳本。佇列與呼叫意圖仍在 PostgreSQL，重啟不代表重送未知結果。

## 心跳與測試隔離

- `/api/runtime/workers` 使用資料庫時鐘，45 秒沒有心跳即離線。正常停止會標示 STOPPED，不必等待 TTL；觀察模式在線但 `can_dispatch=false`。
- 心跳僅證明近期程序可連到平台資料庫，不證明模型帳號、Hop、Vertica 或 Release 正常。
- `runtime-temp/local-sa-worker/service.json` 與相鄰日誌是啟停記錄，不是存活證據；實際程序與 API 狀態才是依據。
- 執行隔離 PostgreSQL 測試前必須停止所有原生／容器 Worker。測試 fixture 會拒絕在近期有 Worker 心跳時建立合成工作，避免真實 Worker 領取测试資料。
- `worker-lifecycle.spec.ts` 是明確啟用的 Windows 觀察模式啟停測試；不派發模型，也不會中止既有使用者 Worker。

## 結果處理

- `VALIDATED_NOT_APPROVED` 只代表輸出結構與版本驗證通過；仍須閱讀 SA 的 `NEEDS_INPUT` 或 `READY_FOR_REVIEW` 建議。
- 排隊中可取消；已領取、逾時或結果不明不能用「取消未呼叫」掩蓋。
- 相同 Run 不會建立第二次呼叫。需要補正時建立新 revision，重新核准與授權。
- 不要直接重跑結果不明的工作。先在 Copilot 本機紀錄及平台事件核對；本輪尚未提供完整人工核對介面。
- 費用依 Copilot 帳號與 CLI 回報，未知用量不當零；目前無 CLI 輸出 Token 硬上限承諾。

完整真實驗收見 [單次驗收報告](verification/copilot-sa-2026-09-13.md)。
