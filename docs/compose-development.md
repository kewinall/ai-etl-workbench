# Compose 開發基準

這是 M0 的隔離開發環境，不是已驗收的完整平台。舊 Windows 服務不需停止。

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
PostgreSQL 與 API 不發布 host port。既有 Vertica 尚未接入本階段。

初始化容器只在 secret 不存在時產生 PostgreSQL 密碼及 AES-256 主金鑰；不輸出其值、不在映像中保存。API 使用非 root UID 10001。

## 持久化與升級

五個具名 volume 分別保存平台 DB、機密、上傳暫存、Hop 產物與輸出。
`docker compose stop` 不移除資料。**不要使用 `down -v` 清空環境。**

Migration 使用 advisory lock、每檔 checksum 與交易記錄，第二次啟動不重跑既有 SQL。若已套用 migration 被修改、缺失或版本順序錯誤，停止升級。若遇到舊資料庫但沒有 migration ledger，拒絕自動執行；須先備份並經過獨立 baseline 採納流程。不要手動偽造 ledger 繞過。

本階段沿用 001–020 的歷史 migration，其中含合成展示資料；只在此新空白 DB 初始化一次。尚未重構為純控制 schema，不應拿來初始化正式業務 DB。

## 執行狀態

`/api/health` 是程序存活；`/api/ready` 會確認 DB／基本 schema，並顯示 `execution_enabled`。
目前 Compose 固定停用 Task 執行與範例表重建，Worker 放在可選 `execution` profile。Linux Hop、隔離 QA 及持久化 Task Controller 完成前不要解除保護。

Worker Dockerfile 暫以現有 WSL Hop 2.12.0 為基準；含 Java／Hop 不等於流程相容性已驗收，也尚未提供 Vertica JDBC 配置。M2 必須處理版本選定、JDBC、per-run metadata、來源掛載與參數化。

## 備份與機密

真正的還原需要 DB、產物與機密 volume 的一致備份。機密備份必須獨立保管，不可加入 Git 或客戶 Release。備份／還原自動化與舊資料遷移尚未驗收，勿用本基準替代原服務。
