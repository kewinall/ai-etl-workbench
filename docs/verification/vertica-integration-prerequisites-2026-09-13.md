# Hop／Vertica 真實整合前置盤點

2026-09-13 唯讀盤點：

- `vertica-25.3` 容器運行且 health healthy；容器內 `vertica --version` 實測為 **25.3.0-2**。
- `hop-server` 使用 `apache/hop:2.12.0`，運行中。
- Workbench API 網路為 `ai-etl-workbench_default`；Hop 為 `apache-hop-server_default`；Vertica 為 `vertica_docker_default`。不同網路本身不證明 TCP 完全不通，但沒有驗證平台使用哪個可達位址。
- 正式 `/api/settings/groups` 回應包含 data_connections_targets；其中 etl_qa 目前是 String，不是 execution_settings resolver 所需的 connection_id／host／port／database／user 結構。因此不能把它當作已配置的 ETL 連線。

沒有讀取容器環境中的密碼、變更 Docker 網路、呼叫資料库或執行 DDL／DML。此盤點不是 connection health test、Hop JDBC 驗證或 ETL 成功。

## 需決定／設定

確認是否以目前本機 vertica-25.3 為隔離 Pilot 驗收目標，並在平台設定中心填妥專用測試連線及密鑰（不要在對話貼密碼）。之後方能測試實際連通、權限、來源／目標註冊、Hop JDBC metadata 與專用測試資料寫入。

不默認既有容器的所有資料可被修改；仍限制平台管理測試範圍，重建遵守 ai_sample／同 Project／已登錄條件。

使用 Vertica router／integration 技能時確認其離線資料限定 24.4.x，所以未將其相容性或預設值套用到此 25.3.0-2 實例。後續版本相關設定須依實際驅動與 runtime 證據驗證。

此項外部設定缺口不表示所有 P0–P3 工程工作均被阻擋；來源不可變綁定、執行控制等實作仍未完成。整體目標維持未完成。
