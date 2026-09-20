# 標準答案保存層驗證

## 最新核准與合併驗證

Migration 034 與內部 approve_oracle 已部署：人工確認比對基準時，需目前規格、最新答案版本與正確 document checksum；答案核准不是 QA 或 Release 通過。新增答案不繼承核准，規格更新後舊答案不可再保存／核准，歷史讀取仍可用。核准記錄不可 UPDATE。

最新 PostgreSQL 合併測試（oracle_store、approved_candidate、specification_api）：10 passed，2.26 秒。涵蓋同步兩次保存同內容只產生一版、核准指紋錯誤、舊版拒絕、規格異動失效及加密歷史回讀。CONTROL Worker 已恢復，ready、execution_enabled=false。

本機後端全套（排除 test_api.py，DB／原生整合關閉）：353 passed、73 skipped，5.20 秒。另行開啟的無網路原生 Hop 測試：4 passed，16.16 秒，涵蓋 CLI、metadata、固定輸出名稱／順序、版本化標準答案及來源暫存。不是 Vertica 寫入。

網站/API 操作、答案值域完整驗證、正式執行結果擷取、QA evidence 保存與交付仍未完成。下列文字保留較早保存層階段狀態，不能据此否定上列已加入的內部核准能力。

Migration 033 已套用至隔離 Pilot PostgreSQL。result_oracle 歸屬既有 specification，透過規格關聯到 Task／Run／Project；不另建 Task 系統。

保存前重新核對當前規格核准、來源設定／命名版本、答案文件指紋、輸出欄位順序及編譯器支援型別。答案內容加密；公開回傳與事件僅含 ID、版本、指紋及未核准狀態。同規格連續相同內容重送不新增版本，修改答案保留舊版；UPDATE 由資料庫 trigger 拒絕。

test_oracle_store_integration.py 實際隔離 PostgreSQL 測試通過（0.70 秒），涵蓋未核准規格拒絕、型別不符拒絕、加密回讀、連續同內容重送、舊版保留、跨 Task 讀取拒絕與 UPDATE 拒絕。測試只清除自己建立的控制資料，沒有刪除既有 Task 或連接 Vertica。

已部署 API／CONTROL Worker，服務 ready、execution_enabled=false。無公開 oracle API、網站表單、答案人工核准、正式 QA 保存或 Release 接通；本次不是完整 P1／P2 驗收。型別檢查是分類一致性，尚未涵蓋目標型別的值域、VARCHAR 長度與 NUMERIC precision/scale 約束。
