# 第 20 案：NULL 分組的失敗診斷與修正交付

驗證日期：2026-09-27。這是既有 `standard-v1` 正式 cohort 的 `recovery-null-group`，不是新增替代案例。

## 固定需求與答案

- CSV 有三列，category 分別為空、A、空；空值依既定契約轉為 NULL。
- 不篩選、不去重；SQL_NULLS 分組、COUNT_ROWS，禁止以 COUNT_NON_NULL(category) 取代。
- 輸出 category VARCHAR(32) NULL、row_count BIGINT NULL，APPEND 至本案例專用 ai_sample 新目標。
- 固定答案是 NULL 組 2、A 組 1，EXACT_MULTISET 忽略列序但保留 NULL、型別與重複。
- 執行前逐項核對已登錄 definition 與固定 corpus，並核對 oracle checksum；答案不取自模型或執行結果。

## 真實驗收證據

| 階段 | 本次結果 |
|---|---|
| 初版 SA / Developer | 真實 Copilot gpt-5.4，各一次，無自動重試；SA v5 無缺口，Developer v4 規格符合固定需求 |
| 受控故障 | 新建且為零筆、同專案登錄的專用表，category 改名為 category_missing_fault；原 HPL 未改動，不 DROP 表 |
| Hop 失敗 | exit 1、errors 1；COLUMN_NOT_FOUND，日誌行 16/23/43；不自動重跑 |
| 失敗核對 | 執行器已停止，另開連線讀取 0 筆與缺欄位結構；核對後 CLOSED_WITHOUT_RETRY，保留失敗表及紀錄 |
| 修訂 | 新 revision、新目標、新輸入核准；不重用原版核准 |
| 修正版 SA / Developer | 真實模型各一次，SA 無缺口；規格仍為 SQL_NULLS + COUNT_ROWS，無額外篩選 |
| Hop / Vertica | 真實執行完成；標準答案 2 組、實際 2 組，EXACT_MULTISET MATCH，缺少／多出均為 0，BOUND_PLATFORM_TARGET |
| QA | 真實 gpt-5.4、prompt v9，PASS、issues 空；引用規格、節點、執行、結果與來源證據。此建議不直接授予交付權限 |
| 可攜性 | 候選套件在隔離環境重播 PASS，不重跑原目標 |
| 正式交付 | 依 Operator 的範圍授權確認綁定版本；RELEASE_READY；實際下載 ZIP，雜湊與 API 一致 |
| 網站 | 真實唯讀失敗／修訂歷史、日誌診斷、父子關聯、返回、390/768/1440 寬度；1 passed（4.4 秒），無寫入請求 |

執行環境由故障觀測確認為 Vertica 25.3.0-2。欄位更名操作參照 24.4.x 離線官方 SQL 文件（PDF 1093 頁），並以本次實際執行結果驗證，不假定版本行為完全相同。

ZIP 正好包含 pipeline.hpl、workflow.hwf、vertica-ddl.sql、SDM.xlsx、parameters.example、release-manifest.json。下載後內容篩檢通過；單獨內容篩檢不等於可攜性驗收，可攜性另有本次隔離重播證據。原始 ZIP、來源資料、連線、Task/Run ID 與私有日誌不提交 GitHub。

## 整體狀態與下一步

本次重新查詢 20 個正式案例最新版的 release API：19 個 RELEASE_READY，第 19 案 `recovery-full-projection` 為 PREREQUISITES_REQUIRED（QA 列序歧義尚未解除）。沒有排除失敗案例，也不把 19/20 描述成首次通過率或工時改善率。

第 19 案需先確認「依序」的業務意義，再使用已新增的 QA 修訂入口；不得修改凍結答案或直接強制 PASS。人工基準、完整成效指標與報告、全平台驗收缺口及第 7 階段維運／還原仍待完成。knowledge-workspace 尚未同步；此去識別化文件保存本階段接續狀態。
