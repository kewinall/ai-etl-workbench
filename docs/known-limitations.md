# 基準版本與已知限制

本 repository 是既有 v2 測試程式的版本控制基準，不表示功能重構或端到端驗收已完成。

## 目標

- 本機單一 Operator、多 Project；PostgreSQL 保存控制資料。
- Vertica 作為主要 ETL 來源範例表、目標與 QA 資料庫；Apache Hop 執行 ETL。
- AI 協助語意理解，deterministic code 控制契約、產物與交付。
- 不要求 Hermes、MCP Server 或多 Agent framework。

## 最新狀態（2026-10-11）

- 前端多代元件與 runtime 覆寫已完成引用稽核並移除；目前入口只保留明確引用的有效元件。見 [UI 收斂紀錄](verification/ui-simplification-2026-10-11.md)。
- 狀態判定統一由 workflow-status 彙整（逐操作資格、已交付只讀）；專案摘要／篩選／卡片共用同一結果。5197 已部署 `3f1a312`，包含管理入口、資格缺漏停用、退回／失效版本狀態、Pilot 執行準備與協作時間軸，以及第三輪規格刷新／SA 守門補正；已交付案例的唯讀部署回歸通過，見 [部署驗收](verification/5197-deployment-acceptance-2026-10-11.md)。
- 受管理工作區在操作資格缺漏或回應版本不符時一律停用寫入（「操作資格尚未確認」）；規格保存／核准 API 已在同交易內驗證同 Run 有效 SA 核准；其他寫入 API 的逐項拒絕覆蓋仍未完成，不以唯讀彙整取代既有後端檢查。
- 已交付版本目前不能建立修正版或新準備版本，畫面明示限制；REPLACE／UPSERT 不可選為新版執行方式（僅保留歷史意圖）。
- 寫入型 live 瀏覽器測試為明確 opt-in（`WORKBENCH_ALLOW_SYNTHETIC_UI=1`、`WORKBENCH_TEST_CONTROL_WORKER=1`），只可在隔離 DB 執行。
- 仍未完成：JSON／資料表完整執行、REPLACE／UPSERT 執行、維運復原、完整列印報告、人工成效基準。

## 尚待修正與驗收（2026-09 前盤點，保留歷史）

- （2026-10-11 已處理）前端多代元件與路由覆寫；專案 CRUD、歷史 Task 與節點詳情仍以各案證據為準。
- 設定保存與執行讀取、AI profile／secret 使用尚需統一；設定檢查不等於真實模型連線成功。
- Requirement revision、NamingContract 確認的 UI 流程與 compiler 串接尚未完整。
- Release DDL 欄位分隔、manifest checksum 與敏感資訊檢查需修正。
- 型別辨識、Join 業務規則確認、失敗恢復與跨產物一致性需補測試。
- 啟動腳本、範本和部分 fixtures 仍含開發用絕對路徑；尚未驗證乾淨機器部署。

## 驗收界線

Unit tests 與 frontend build 通過，不代表真實 Bedrock、Hop、Vertica 或使用者流程已通過。正式驗收須包含設定讀回、UI 操作、API、執行紀錄、資料庫結果與交付 ZIP 的一致性。

請勿將真實資料、機密、runtime trace、資料庫備份或未清理的 ETL 產物提交至 repository。
