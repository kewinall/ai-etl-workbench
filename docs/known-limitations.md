# 基準版本與已知限制

本 repository 是既有 v2 測試程式的版本控制基準，不表示功能重構或端到端驗收已完成。

## 目標

- 本機單一 Operator、多 Project；PostgreSQL 保存控制資料。
- Vertica 作為主要 ETL 來源範例表、目標與 QA 資料庫；Apache Hop 執行 ETL。
- AI 協助語意理解，deterministic code 控制契約、產物與交付。
- 不要求 Hermes、MCP Server 或多 Agent framework。

## 最新狀態（2026-10-11）

- AI Profile 保存後離開保護的時序問題已修正並部署5197 web（d3a2e4d/index-CQpDjssy.js），保存成功立即解除本表單保護，其他草稿與保存失敗仍保留提醒；build及隔離回歸已驗證，compiled合成4PASS、新三案與原三案各10PASS。八Release與九保護服務不變；見 verification/v2-profile-deployment-2026-10-11.json。執行／部分提交live測試已移除舊入口與固定5197，改用專用URL守門；未執行新的真實故障寫入。保留真實部分提交紀錄已完成新版唯讀回歸，67張表指紋不變，沒有重啟Vertica或重跑ETL；見 verification/v2-partial-readonly-2026-10-11.json。
- 唯讀來源資格一致性修正：所有非DOWNLOAD資格與next_action操作資格明確停用，真正保存的下載資格保留。新增測試重現current QUEUED原來源仍宣告可寫；修正後proxy/workflow39PASS，完整隔離backend2134PASS/139skip，0migration。此後端修正尚未部署5197 API；原GET-only路由仍拒絕寫入，未擴大來源allowlist。
- d5e7de8 SDM背景提示修正已部署5197（1099215工程批，compiled SDM3PASS、新三案10PASS及原三案10PASS）。新PG17實際程序死亡與網站結案已通過，但角色為synthetic，沒有Hop／Vertica／真實模型，不能代表新的部分寫入驗收；證據見 verification/v2-owner-death-ui-2026-10-11.json。

- v2 後續：已停用舊 Task 執行／補正／驗證入口，Run 工作流寫入會依既有交付記錄守門；工程 source `a7a666f` 已部署 5197。2026-10-11 新 CSV／Excel／LEFT JOIN 三案已經正常網站與真實模型、Hop、Vertica、QA、隔離可攜驗證及正式 ZIP，原目標各寫入一次，固定答案 2／2／5 筆完全符合。七階段三寬度／鍵盤／下載回歸 10 PASS，五個既有 Release 指紋及寫入次數不變。見 [後續開發驗證](verification/v2-followup-development-2026-10-11.md)。這是三個受控合成案例的驗收，不代表下列獨立里程碑完成。
- 後續介面：新 Task 不再建立舊流程空白節點；空白舊版區隱藏，真實歷史節點及下載仍保留。未套用執行流程的驗證策略僅顯示保存值，無儲存入口。


- 前端多代元件與 runtime 覆寫已完成引用稽核並移除；目前入口只保留明確引用的有效元件。見 [UI 收斂紀錄](verification/ui-simplification-2026-10-11.md)。
- 狀態判定統一由 workflow-status 彙整（逐操作資格、已交付只讀）；專案摘要／篩選／卡片共用同一結果。5197 API 為 `a7a666f`，前端為 `d3a2e4d`（`index-CQpDjssy.js`），包含舊入口退場、交付守門、空白歷史隱藏、草稿與錯誤保留、失敗診斷去重，以及 Hop／QA／比對恢復／QA核准／SDM回應不明時先GET核對、禁止自動重送。九個受保護服務及八個新舊正式成果不變，見 [最新部署讀回](verification/v2-profile-deployment-2026-10-11.json)。
- 受管理工作區在操作資格缺漏或回應版本不符時一律停用寫入（「操作資格尚未確認」）；規格保存／核准 API 在同交易內驗證同 Run 有效 SA 核准；本輪覆蓋 21 項已交付拒絕及 9 種 API × 3 種前置條件拒絕。這是 Task/Run 工作流範圍，不是整個平台全部 API 的安全認證；不以唯讀彙整取代後端檢查。
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
