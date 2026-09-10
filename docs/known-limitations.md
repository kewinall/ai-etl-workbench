# 基準版本與已知限制

本 repository 是既有 v2 測試程式的版本控制基準，不表示功能重構或端到端驗收已完成。

## 目標

- 本機單一 Operator、多 Project；PostgreSQL 保存控制資料。
- Vertica 作為主要 ETL 來源範例表、目標與 QA 資料庫；Apache Hop 執行 ETL。
- AI 協助語意理解，deterministic code 控制契約、產物與交付。
- 不要求 Hermes、MCP Server 或多 Agent framework。

## 尚待修正與驗收

- 前端仍有多代元件與路由覆寫，需完整驗證專案 CRUD、歷史 Task 與節點詳情。
- 設定保存與執行讀取、AI profile／secret 使用尚需統一；設定檢查不等於真實模型連線成功。
- Requirement revision、NamingContract 確認的 UI 流程與 compiler 串接尚未完整。
- Release DDL 欄位分隔、manifest checksum 與敏感資訊檢查需修正。
- 型別辨識、Join 業務規則確認、失敗恢復與跨產物一致性需補測試。
- 啟動腳本、範本和部分 fixtures 仍含開發用絕對路徑；尚未驗證乾淨機器部署。

## 驗收界線

Unit tests 與 frontend build 通過，不代表真實 Bedrock、Hop、Vertica 或使用者流程已通過。正式驗收須包含設定讀回、UI 操作、API、執行紀錄、資料庫結果與交付 ZIP 的一致性。

請勿將真實資料、機密、runtime trace、資料庫備份或未清理的 ETL 產物提交至 repository。
