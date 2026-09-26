# 第 4 階段：失敗診斷與受控修訂

2026-09-26 實作與測試，2026-09-27 補存紀錄。上一輪核准服務額度限制曾阻止文件保存；不影響下列已執行測試，但當時未上版。

## 已接通，尚非真實情境驗收

- 修正 RunQueue.revise 只允許需求補正的限制：已核對結案的 FAILED/HOP_EXECUTION 可建立子 revision。
- 必須保留原 outcome、write marker、輸入與歷史，具備 reconciliation、沒有有效 lease，並使用 ai_sample 不同的新目標；不重跑原 Run。
- 新版不沿用核准／Gate／執行證據，重新確認後從 Gate 開始。
- 唯讀 diagnosis API 核對加密日誌與終態事件 checksum，只輸出固定訊息、行號與指紋，不公開原始 SQL／資料／密碼。
- 網站標示診斷為程式規則而非 AI；診斷不等於已證明根因或回滾，不授予自動修復權限。
- 結案後顯示修訂入口，提示新目標及重新核准。

## 已執行驗證

- 隔離 PostgreSQL 回歸：1031 passed、46 skipped、1 warning，23.30s，exit 0。
- 診斷保密／未知／指紋變更：3 passed，0.15s。
- TypeScript／Vite build 通過。
- 瀏覽器合成 API：核對、衝突、診斷行號、修訂提交、390px 無溢出，2 passed，7.4s。
- API/control-worker/web 與 Worker 映像已重建部署；未呼叫模型、未重跑既有交付。

瀏覽器測試只使用既有 Task 導覽，攔截寫入，不改真實 Run。控制平面測試不等於 Hop／Vertica E2E。

## 下一步與未完成

建立獨立 Task、事前標準答案與新測試目標，經真實 SA／Developer 核准，在受控測試範圍製造缺欄位失敗。
保存 Hop 日誌、目標結構與筆數，核對引擎停止後結案，再建立新目標 revision，重新核准與真實執行／QA。
須證明新結果正確、原失敗仍可追溯，才可宣告第 4 階段通過。目前第 4–7 階段均未完成。

## 2026-09-27 真實案例已建立與 SA 通過

- 固定合成輸入與事前兩筆答案：`backend/tests/fixtures/pilot_missing_column_case_v1.json`。
- 已建立獨立 Project／Task／Run，識別碼、輸入／設定指紋與核准綁定留在本機平台紀錄。
- 輸入已核准，Gate CHECKED。
- 真實 SA：READY_FOR_REVIEW，無 issue；未執行工具、未自動重試。
  模型用量明細留在平台 trace，不公開內部識別碼或用量 metadata。
- 首次誤用 DW_DM 分類而被 API 422 拒絕，未建立 Task；改用單來源 STAGE 後建立成功。
  Project 沿用，合成 CSV 上傳兩次；沒有刪除既有來源。

尚未做 SA 交接核准、Naming Contract、Developer、規格／Oracle 核准、Hop 或故障注入。
下一步從平台既有缺欄位驗收 Run 繼續，不重建案例、不再次呼叫 SA；測試限 ai_sample 專用新目標。

## 2026-09-27 規格與答案核准完成

WSL 曾停止，先確認 Stopped 後恢復既有容器與資料卷；沒有重建 DB、重複模型或 ETL。
暫時存活程序不是正式維運方案，仍須在第 7 階段完成操作者啟停驗收。

原 SA 紀錄完整，完成綁定版本的交接核准；兩欄 Naming Contract 已確認。
真實 Developer 一次呼叫後，產生直接投影 record_key/label 的單來源 APPEND 規格，
無篩選／Join／彙總，通過 deterministic validator 並保存；依委派核准規格。
事前合成兩筆標準答案已綁定該規格／命名版本，保存及核准成功。

尚未建立 Hop 派送請求或目標表，沒有故障注入或實際寫入。
下一步需受控、單次故障測試：僅此新建且平台登錄的空目標，保留原編譯 HPL，
在明確測試程序中模擬目標欄位不符，驗證 Hop 真實失敗及診斷；不新增一般使用者可任意 ALTER 的 API。
核對結案後的新 revision 必須改用新目標，原失敗表／日誌與證據保留。

## 2026-09-27 真實故障與核對結案通過，修正版待執行

新增 opt-in `app.pilot_failure_probe`：只接受固定合成 CSV checksum、指定新目標命名範圍、
兩欄直接投影 APPEND、原始未寫入 Run 及已核准派送 binding。
正常建立／登錄新表後，再確認同 Project/Task、欄位與空表，僅改名 label 模擬缺欄位；
原 HPL 不變，單次執行、加密日誌保存、無 DROP／重試／自動修復，最後以新 DB session 核對。
沒有對一般 API 新增任意 ALTER 能力。

- 防護單元測試：13 passed（0.35s）。
- 完整隔離 PostgreSQL：1044 passed、46 skipped、1 warning（23.12s）。
- 實際 Vertica：25.3.0-2；文件參考為 24.4.x ALTER TABLE 欄位改名例（官方 PDF p.1093），
  最終結果以實測為準，不推定跨版本相同行為。
- 原生 Hop 真實失敗：exit 1、errors 1、HOP_EXECUTION_FAILED，僅一個 WRITE_STARTED。
- 診斷 API：COLUMN_NOT_FOUND，引用原加密日誌第 14、21、41 行，不公開原始內容。
- 新 DB session 查得 0 筆、欄位 record_key/label_missing_fault；表保留，沒有宣稱所有批次原子回滾。
- 引擎程序結束後，依保存的結構／筆數 evidence checksum 完成核對結案；父 Run 保持 FAILED。
- 已建立同 Task 的修正子 revision，指定不同的新目標；QUEUED、write_started=false，無舊核准。

內部 Run／核准識別碼、指紋留在平台紀錄，不發佈到公開文件。
下一步從既有修正子 revision 繼續輸入核准→Gate→SA→Developer→規格／Oracle→正常 Hop→QA。
不要再次呼叫故障工具或重建原案例。第 4 階段仍待修正版成功及 UI 歷史驗收。
