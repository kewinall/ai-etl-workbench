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

## 2026-09-27 修正版真實 Hop 比對通過，QA 證據仍待補齊

- 第一個修正需求誤寫為「依已核准 DDL 建表」，SA 正確要求補正：SA 階段沒有該產物。
  保留 NEEDS_INPUT，建立新 revision，明定兩欄 VARCHAR(32) NULL 與後續編譯 DDL 的順序。
- 新 revision 的真實 SA 無 issue；Developer 產生兩欄直接投影 APPEND，無 filter／join／aggregation。
  規格與事前固定兩筆 Oracle 已依委派權限核准；沒有沿用舊 revision 核准。
- 正常 Hop Worker 單次建立新受控目標並執行：exit 0、errors 0、三節點證據完整。
  新 DB 查詢的精確多重集合比對 MATCH：預期 2、實際 2、缺少 0、多出 0；來源綁定通過。
- 真實 QA 返回 NEEDS_REVIEW，未做 QA／Release 核准，沒有重跑 Hop。
  單來源 execution_details 尚未帶入已存在於多來源分支的 runtime_options；
  QA 另要求空字串／保留空白／錯誤及過長值處理、header 對應方式、DDL nullable／無主鍵的證據。
- 實際網站「執行與 QA」已確認 2／2 比對、來源核對、重新讀取後 NEEDS_REVIEW 與四項問題可見；
  版本選單仍保留原 FAILED、補正 CANCELLED 與最新 NEEDS_REVIEW。
  這不等於已完成所有節點／窄版面／交付互動回歸。

下一步：補齊單來源、相同已執行 HPL 的唯讀 QA context，以及有指紋綁定的 DDL／header 證據；
保留舊 context checksum，新增嚴格的同次執行 enrichment 與負向測試。
檢查／補充實測證據後再授權 QA 複核，不以修改提示強迫 PASS，不改需求以避開問題，
不重新執行已成功的目標。第 4 階段仍未完成，第 5–7 階段不受此 checkpoint 宣稱完成。

## 2026-09-27 單來源 QA 補證與正式交付通過

加入 QA context v6 的 `single_source_contract`：驗證原 HPL 選項、來源欄位指紋、
精確區分大小寫的 positional header preflight，以及同 Run target claim 的 DDL 指紋。
DDL 證據標示平台登錄範圍，不聲稱即時 catalog 或外部 DBA 未修改；獨立引擎探針仍非此 Run 實測。
v3→v6 僅可移除新增欄位還原完整舊 context 才允許補證，不能改寫需求／執行／比對；
既有 PASS 的 v3 context 保留版本。Prompt v6 說明證據範圍，不要求模型 PASS。

- 針對測試：38 passed（0.57s），含 DDL 與實際 delivery compiler 一致、錯誤 claim／header 拒絕。
- 隔離 PostgreSQL 全套：1059 passed、46 skipped、1 warning（23.98s）；其後新增兩項上述單元測試另行通過。
- API／Worker 重建部署。三個既有正式交付案例皆仍為 APPROVED_CURRENT。
- 此修正版真實 QA v6 PASS、無 issue；v5 NEEDS_REVIEW 與原日誌原樣保留。
- 依使用者委派核准 QA，產生綁定 SDM、候選包；既有隔離 Vertica 啟動及唯讀連線通過。
- 新候選 HWF 單次隔離執行 PASS，通過固定標準答案；正式 Release 核准後 RELEASE_READY。
- 真實下載 ZIP 指紋與 API 相符，六個固定成員、五份 artifact 的大小與 checksum 均驗證。
  內部識別碼與 ZIP 指紋僅留本機平台，不新增至公開文件。
- 原失敗仍 FAILED，修正版原始 Hop 僅一次 WRITE_STARTED，沒有重放原目標。

下一步完成此案例真實網站歷史切換、節點／診斷／交付與窄版回歸，再判定第 4 階段。
第 5–7 階段仍未完成。Workspace CURRENT 與 tasks.yml 最新同步因既有內容含敏感 metadata
遭安全審查拒絕，未改用其他方式繞過；後續須先取得安全的去識別更新方案。

## 2026-09-27 歷史 Run 節點與網站案例驗收

實際瀏覽發現產物頁只有舊版節點，且錯誤顯示新版編譯尚未接通。新增唯讀 Run
產物檢視，以原授權 specification／HPL checksum 核對重建內容，並以終態日誌指紋
核對實際節點計數；無計數時不補零，不授予執行或交付權限，不揭露原始機密日誌。

- 原失敗／修正版可切換；原 target errors 1、written 0，修正版 errors 0、written 2。
- 點選節點可顯示計數及設計；失敗診斷仍可見缺欄位證據及行號。
- DDL 可展開，顯示兩欄 VARCHAR(32) 定義；旧版節點保留並標示不代表新版 Run。
- 390px 窄版檢查沒有文件橫向溢出；修正節點按鈕 badge 擠壓、斷行的排版。
- 返回專案歷史、重新進入 Task、交付頁及瀏覽器返回／前進路由正常。
- 交付頁顯示正式核准與可攜 PASS；實際點擊正式 ZIP 連結收到瀏覽器下載事件。
  ZIP 內容與指紋的 API 驗證沿用上述同一 Release，沒有重跑模型或 ETL。
- 新增 5 項單元測試通過；前端 TypeScript／Vite build 通過。
- 隔離 PostgreSQL 全套：1066 passed、46 skipped、1 warning（23.48s）。

第 4 案例的失敗、補正、真實執行、QA、Release 與上述網站路徑已有證據。
不將此範圍外的專案 CRUD、設定儲存重載或整个平台回歸視為通過。
下一步第 5 階段：修正協作頁過時未接通提示、舊版產物空狀態與正式交付狀態呈現，
並完成專案／設定與全部主要操作的回歸。第 5–7 階段仍未完成。

## 第 5 階段：協作紀錄修正 checkpoint

協作頁移除 Developer／QA 尚未接通的錯誤提示，分別讀取既有唯讀 API；
角色查詢失敗獨立顯示，不偽裝成沒有呼叫紀錄。呈現模型、保存時間、耗時、
有提供的 Token 與 QA 建議，保留每次 QA 歷史，並明示不代表人工核准。

TypeScript／Vite build 通過；只重建並部署 web。實際瀏覽同一修正版，
Developer 紀錄、最新 QA PASS 及先前 NEEDS_REVIEW 均可見；沒有額外模型或 ETL 呼叫。
此 checkpoint 不代表第 5 階段全數通過；下一步仍為概覽／專案交付狀態、
舊版空狀態與完整 CRUD／設定回歸。

概覽另加入最新 Run 的唯讀交付證據核對，只有 API 同時返回 RELEASE_READY、
release_ready 與正式 Release 紀錄才顯示已核准；讀取失敗明示無法確認。
保留原控制流程狀態，沒有竄改歷史。TypeScript／Vite build 與 web 部署通過；
實際網站確認「正式交付已核准」，點擊「查看交付證據與下載」進入同 Task 交付頁。
專案清單交付摘要與完整 CRUD／設定回歸仍待完成。
