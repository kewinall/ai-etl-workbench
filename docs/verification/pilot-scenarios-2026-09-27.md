# 凍結 Pilot 情境證據重驗

2026-09-27：正式案例量測新增唯讀情境重驗，不由最終 Release 成功推論所有前置情境已通過。

## 檢查範圍

只接受登錄 definition 與內建 standard-v1 corpus 完全一致的集合案例；其他自訂版本顯示 UNSUPPORTED_CATALOG，不套用不合適的判定。保留固定 20 案分母。

- 從持久化 attempt ordinal 選取最新版，核對目前輸入／設定，沿 parent_run_id 追溯。無關分支不能提供前置證據，缺失或循環父版本不能通過。
- 最新版來源欄位與內容 checksum 必須符合凍結 fixture，且 Requirement Gate 保存的 UPLOAD_BYTES_VERIFIED 證據需匹配每個 source reference。
- 重新取得已綁定、核准且加密保存的 execution oracle；以固定 corpus 字面答案對照其型別、NULL、重複及多重集合，不用實際執行輸出或模型回覆建立答案。原始答案不放入量測 API。
- 需求缺口：父版本的原始缺值、指定欄位 issue、NEEDS_INPUT 與控制事件都需存在，而且未開始寫入。
- 語意植錯：父版本需未開始寫入；拒絕事件的 input/settings/attempt checksum、欄位路徑、預期／實際值與節點／需求引用需符合指定植錯。GE→GT、LT→LE、LEFT→INNER、100→20、COUNT_ROWS→COUNT_NON_NULL 分別比對，不把任意錯誤當指定缺陷攔截。
- 失敗修正：核對父版本明確 HOP_EXECUTION_FAILED、缺欄位植入→失敗→新連線觀測→核對結案的事件順序、dispatch checksum、觀測 checksum、核對紀錄及不同的 ai_sample 目標。重新解密核對原日誌 checksum 與 COLUMN_NOT_FOUND 行號，不輸出日誌內容。未知結果不冒充確定失敗。
- 以上證據與最新版 Release gate 均符合，才顯示 SCENARIO_EVIDENCE_MATCHED；任何缺少、變更或讀取錯誤均不計通過。

此讀取器不修改狀態、核准、歷史事件或資料表，不呼叫模型、不重播 ETL。它重驗持久化驗收證據，不宣稱重新執行或新的即時資料庫內容驗收。

## 驗證結果

新增測試過程先修正測試檔未閉合括號與斷言位置問題；失敗時未部署。最終：

- 新增 19 項來源／父子版本／缺口／語意／失敗修正正反例全部通過。
- 完整隔離 PostgreSQL 回歸：1310 passed、46 skipped、1 warning，26.74 秒，exit 0。
- TypeScript/Vite build 通過；部署前核對无執行中 Run 或 RESERVED 模型。
- 真實 API：來源與固定答案 20 案均匹配，前置情境證據均可追溯；19 案同時具備可交付狀態，因此情境證據符合數為 19/20。
- 第 19 案仍 EVIDENCE_REQUIRED，未放行 QA 或 Release，亦未修改其原需求歧義或凍結答案。
- 真實瀏覽器 1 passed（11.0 秒）：逐案交付 gate 一致；前置證據引用可回讀指定父版本事件；畫面數字、版本連結、返回與 390/768/1440 寬度通過。無寫入請求或頁面錯誤，前後檢查 Run 事件相同。

## 下一步與限制

仍缺第 19 案業務列序釐清、首次通過率的完整判定、人工操作計時／基準、可列印主管報告及第 7 階段維運／還原驗收。用量缺漏持續保留；不由情境符合數推導工時改善。knowledge-workspace 尚未同步。
