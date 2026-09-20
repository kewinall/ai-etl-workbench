# P0 常駐 Worker 與存活狀態驗收

## 已實作

- `027_worker_presence.sql` 保存 CONTROL、SA_LITELLM、SA_COPILOT 的程序心跳；使用 PostgreSQL 時鐘，45 秒失聯即不再視為在線。
- `/api/runtime/workers` 區分尚未啟動、離線、近期在線與是否為派發模式。資料庫不可用回傳 503，不偽裝成全部離線或沿用舊成功狀態。
- Task 與平台設定中心顯示 Worker 狀態，每 10 秒讀取；明示不等於模型或 ETL 健康。
- Windows Worker 支援常駐輪詢；只有 `--allow-model-dispatch` 才領取已授權 Copilot 工作，預設觀察模式不呼叫模型。既有 Run、授權、租約、不可重送政策不變。
- 隱藏啟動／安全停止腳本，拒絕重複啟動，核對程序及停止檔路徑。正常停止等待目前呼叫完成，不強殺／重播。
- Worker 程序心跳與每個工作租約分開。正常停止的 instance 不可復活；重啟建立新 instance。舊 `worker_connected` 固定假值改為 null，存活查詢以 runtime API 為準。

## 驗證證據

| 驗證 | 結果與範圍 |
|---|---|
| 選定本機回歸 | 138 passed；不呼叫真實模型 |
| 隔離 PostgreSQL | 32 passed；時鐘、觀察／派發區別、正常停止、過期、授權及既有 Run；模型結果使用合成資料 |
| 真實 Windows lifecycle | 1 passed，約 1 分鐘；啟動觀察程序 → 網站在線 → 正常停止 → 重啟 → 強制終止該測試程序 → TTL 離線 → 再啟動 → 正常停止 |
| 網站回歸 | 6 passed（16.0 秒）；真實 Copilot 與 lifecycle 兩個需 opt-in 的案例跳過，沒有再消耗模型額度 |
| 390px | lifecycle 測試檢查設定中心無整頁水平溢出 |
| 啟停腳本 | 觀察模式 PID 36104 實際存活、日誌 OBSERVING、API can_dispatch=false；停止程序成功。之後啟動派發模式 PID 56480，重複啟動被拒絕 |
| 最終服務 | 驗收當時 CONTROL 與 SA_COPILOT 均 ONLINE、active_instances=1、can_dispatch=true；SA_LITELLM 尚未啟動。Copilot 日誌 STARTED／IDLE，無新模型工作 |

PID 是驗收當時值，不應用作日後停止指令。日後必須核對服務狀態檔、實際程序及 API。

## 不代表完成的項目

本輪真實程序的強制中止使用 **觀察模式**，沒有中止真實付費模型請求。工作租約失效與不重送由隔離 PostgreSQL／合成回應測試驗證；不能把兩者當成真實模型執行中斷 E2E 已完成。

上一輪唯一真實 Copilot SA 呼叫仍為 [單次驗收](copilot-sa-2026-09-13.md)，模型判斷 NEEDS_INPUT，非需求或 ETL 成功。本輪不新增真實模型呼叫。

尚未加入 Windows Service／開機自啟、完整人工核對 UI、Bedrock 真實呼叫，以及 Hop／Vertica／QA／Release 的 P1–P3 全流程。P0–P3 仍不可宣告完整驗收。
