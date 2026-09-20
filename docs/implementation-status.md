# Workbench 重構追蹤

本文件記錄實際實作與驗收，不把建置通過當成完整平台完成。

2026-09-11：已進入內部 Pilot P0，新增設定／模型邊界與經真實 PostgreSQL 測試的佇列基礎。最新結果與未完成項目見 [Pilot 實作紀錄](pilot-implementation.md)；下方保留前階段紀錄。

| 階段 | 狀態 | 尚未完成 |
|---|---|---|
| M0 部署與資料保護基準 | 進行中：Compose、機密 volume、migration ledger、readiness、隔離驗證 | 舊 DB baseline 採納／歷史檔案遷移、備份還原演練、完整依賴鎖定 |
| M1 專案與設定 | 進行中：專案元件／路由、CRUD、歷史與節點導覽已驗證；設定政策加入共用型別限制 | 連線與 AI 設定解析、執行流程套用、完整設定中心重構與互動驗收 |
| M2 單一 E2E | 待實作 | Gate／Naming／Specification 接通、Linux Hop、Vertica QA、Release |
| M3 複雜 ETL | 待實作 | 多来源、Join／Window／Module 與恢復 |
| M4 知識與診斷 | 待實作 | 核准文件檢索、引用、根因建議 |
| M5 交付穩定化 | 待實作 | 可攜性、敏感資訊檢查、完整回歸 |

## 已確認架構

## 本次驗證紀錄（2026-09-10）

- 後端回歸：48 passed，涵蓋設定契約、專案、部署、Harness、Hop 規則、複雜規格、上傳、範例資料與分析器。
- 隔離 Compose 的 Playwright：3 passed，涵蓋專案新增／編輯／取消／重載、新 Task 歸屬、歷史建立內容／8 個節點／Job／返回，以及設定儲存重載。
- 設定的群組與舊版入口皆拒絕停用 Naming Contract；拒絕後資料不變。測試結束還原原驗證策略。
- Web/API 已重建啟動於 http://127.0.0.1:5183；ETL execution 仍停用。
- 固定政策（ai_sample、snake_case、AES-256-GCM、主金鑰來源）改為唯讀欄位，不代表 AI／連線／路徑偏好已接通執行流程。
- 尚未完成真正 Bedrock → Hop → Vertica → Release E2E；原 Windows 資料不曾遷移或刪除。本階段測試專案與合成 Task 留在隔離 DB。

## 架構原則

- 單一 Operator、多 Project；Docker Compose 主環境。
- Web → API → PostgreSQL 工作佇列 → Worker／Hop → 外部 Vertica → QA／SDM／Release。
- PostgreSQL 只保存平台控制資料；artifact 使用持久化 volume。
- 精選 enterprise-etl-platform 的 metadata／驗證、multi-llm-ai-gateway 的治理、data-platform-mcp-server 的受控 adapter、enterprise-rag-platform 的引用檢索與 agentic-dataops-copilot 的證據診斷。
- 不部署五個完整服務，不導入 Hermes、MCP Server、多 Agent framework 或正式排程。

## 本階段安全邊界

Compose 使用獨立的空白平台 DB，不讀取根目錄 `.env`，不接管原資料庫。
現有 Windows 程式與 Task 歷史仍保留。新容器 `WORKBENCH_EXECUTION_ENABLED=false`，不啟動任何 ETL 寫入；這是過渡保護，不是已完成的 Worker 設計。
