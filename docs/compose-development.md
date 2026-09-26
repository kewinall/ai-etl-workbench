# Compose 開發基準

這是內部 Pilot 的隔離部署入口，不是已完成所有七階段驗收的正式版本。
舊 Windows 服務不需停止；最新證據見 [七階段進度](staged-completion.md)。

## 啟動

在 repository 根目錄，使用可操作 Docker 的 Linux／WSL shell：

```sh
docker compose -f deploy/compose.yml config --quiet
docker compose -f deploy/compose.yml build api web
docker compose -f deploy/compose.yml up -d web
docker compose -f deploy/compose.yml ps -a
curl --fail http://127.0.0.1:5183/api/ready
```

網站預設 `http://127.0.0.1:5183`；可用 `WORKBENCH_PORT` 調整，仍僅綁定本機。
PostgreSQL 與 API 不發布 host port。Vertica 為另行設定的外部測試連線，
不會由此 Compose 自動部署，也不會自動匯入舊資料。

初始化容器只在 secret 不存在時產生 PostgreSQL 密碼及 AES-256 主金鑰；不輸出其值、不在映像中保存。API 使用非 root UID 10001。

## 持久化與升級

五個具名 volume 分別保存平台 DB、機密、上傳暫存、Hop 產物與輸出。
`docker compose stop` 不移除資料。**不要使用 `down -v` 清空環境。**

Migration 使用 advisory lock、每檔 checksum 與交易記錄，第二次啟動不重跑既有 SQL。若已套用 migration 被修改、缺失或版本順序錯誤，停止升級。若遇到舊資料庫但沒有 migration ledger，拒絕自動執行；須先備份並經過獨立 baseline 採納流程。不要手動偽造 ledger 繞過。

目前包含 001–049 migrations，其中早期 migration 含合成展示資料；
只可用新空白測試 DB 初始化，不應拿來初始化正式業務 DB。

## 執行狀態

`/api/health` 是程序存活；`/api/ready` 會確認 DB／基本 schema，並顯示 `execution_enabled`。
預設停用 ETL 與 AI dispatch。執行環境變數、資料庫設定及逐 Run 人工核准
是不同的控制層；單獨開啟 profile 不代表允許任意執行。

建議目前控制流程使用 `pilot-control` profile。它只做初步程式檢查與佇列
管理，不呼叫模型或執行 ETL。`pilot-execution` 為受控 Hop Worker，建置前
先讀 [JDBC 前置條件](worker-jdbc-build.md)。`pilot-ai` 為 SA dispatch，
須另外配置可用模型與明確授權。舊 `execution` profile 保留供歷史入口，
不要把它與新 Pilot Worker 同時開啟作為一般啟動方式。

驗證獨立部署時應同時指定新的 project name 與不同本機埠，例如：

```sh
WORKBENCH_PORT=5194 docker compose -p ai-etl-clean-deployment \
  -f deploy/compose.yml --profile pilot-control up -d --build
```

停止或重啟時需沿用相同 `-p`、profile、埠與檔案；不同 project name 對應
不同具名 volumes。不要對原 Pilot 執行驗證環境的清理命令。

## 備份與機密

真正的還原需要 DB、產物與機密 volume 的一致備份。機密備份必須獨立保管，不可加入 Git 或客戶 Release。備份／還原自動化與舊資料遷移尚未驗收，勿用本基準替代原服務。
