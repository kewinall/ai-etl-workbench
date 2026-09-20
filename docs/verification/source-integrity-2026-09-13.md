# 來源檔案完整性 Gate：2026-09-13

## 已實作

- 受控 upload UUID 與固定檔名讀取，不接受來源 path 作為讀檔指令；檢查大小、SHA-256、一般檔案、symlink/reparse point。
- 只回傳一次讀取且 checksum 符合的 bytes。不是對抗具權限的本機檔案系統攻擊者，也尚未供 Hop 執行器使用。
- CONTROL Worker 取已核准 Run input_snapshot 的來源資訊，執行內容預檢，保存不含資料值或路徑的 source_evidence。CSV 另外驗證明確的編碼、欄位與額外欄位契約。
- 舊來源缺少綁定資訊時不補造核准值，要求重新上傳。兩處前端上傳 mapping 已補存 size。

## 實測

- 37 項本機測試通過，包含真實暫存檔案修改、缺檔、錯誤大小、非法輸入及 Worker 狀態。首次測試揭露循環 import，修正後重跑通過；一次錯誤工作目錄造成的 collection error 不計為通過。
- 新映像下 19 項隔離 PostgreSQL 測試通過，涵蓋 queue 原子操作及兩個新增來源案例：正常內容保存證據；核准後同長度內容變更保存 UPLOAD_CONTENT_CHANGED 並停 NEEDS_REVIEW／NEEDS_INPUT。write_started 均 false。
- 測試用獨立合成資料與暫存檔案；使用既有 fixture 還原設定並清理自身資料，不連接 Vertica。
- api、control-worker、web 已更新；API ready，execution_enabled=false。
- 部署後瀏覽器 10 passed / 2 skipped（29.0s）。本次規格 UI 控制測試 Task TASK-20260913-0095，Run 8029b973-3c53-428b-bf2e-467cc9e6ca0c，specification 5b7f0cea-2bc0-4b5f-988d-2d47b6e4d970。此案例為合成來源規格流程，不是上傳流程。

## 未驗收範圍

- 專屬上傳 UI → 共用 volume → Worker 已於下述追加驗收通過；不是完整 ETL 驗收。
- 預檢後檔案仍可能改變。未來 Hop staging 必須使用再次核對的 byte snapshot，不能直接重開來源 path 並沿用本次 Gate 成功。
- 缺少 metadata 的歷史來源如何重新上傳並保留修訂歷史，需要完整 UI 流程。
- 尚無 Hop／Vertica／QA／Release 成功證據；沒有新增模型呼叫。

## 追加：真實網站上傳驗收

- 首次測試失敗：repository 的 create_task/update_task 丟棄單一來源 sources 清單，導致 CSV Gate 不認得來源、補正表單無 CSV 契約欄位。已改為保留清單，也保留舊頂層欄位供既有流程使用；沒有重寫歷史資料。
- 首次測試超時導致 finally 無法使用已關閉的 request context。已從該次 trace 原始設定回應還原平台設定，取消自身 TASK-20260913-0097 的 Run，保留失敗歷史。加入 10 秒操作 timeout，讓欄位缺失先失敗並有時間清理。
- 修正部署後，網站建立 Task、選擇實際 CSV、提交、確認需求版本、補正寫入／期間／CSV 契約、新版核准、Worker 回讀檔案及 API 取證全部通過，無 browser response mock。
- 第一次成功：TASK-20260913-0098，Run 4ea0d767-eedb-44e8-b65e-3039627672d1，5.6 秒。直接查 PostgreSQL 確認 source_evidence 留存、write_started=false；測試清理後 Run 為 CANCELLED，不是 ETL 成功。
- 檔案 39 bytes、2 筆資料，SHA-256 8f9a819e68e2b4dcd8d098a7d3a838e144a8cc3fb7c70ff2d38965c93868e8c6，來源與 CSV 結構檢查通過。
- 完整瀏覽器回歸 11 passed / 2 skipped（31.7 秒），再次上傳成功為 TASK-20260913-0105，Run fd139047-50aa-4c26-8977-cb54febf0d39。原設定由 finally 恢復，自身未寫入 Run 取消，保留歷史。
- 後續已新增網站來源驗證面板（見下）；缺少綁定的歷史來源重新上傳修訂與 Hop staging 仍待完成。

## 追加：來源證據網站呈現

- RunVersions 顯示 SourceEvidence：檔案 byte 大小、CSV 掃描記錄數、是否完整及可展開內容 SHA-256。掃描記錄數不稱為匯入成功筆數。
- 失敗代碼轉為說明；未知狀態、缺少證據均不視為成功。顯示舊證據不代表目前檔案仍相同；CSV 通過不包含型別或業務語意驗證。
- 網站已部署。完整回歸 11 passed / 2 skipped（34.3 秒）。真實上傳 TASK-20260913-0112、Run a57e7970-c03d-4036-a2ac-ae4823a93dfd，驗證面板 39 bytes／2 筆及 SHA-256 展開，390px document 無水平溢出。
- 截圖保留在 frontend/test-results 的 upload-live 測試目錄。窄版頁面仍較長，資訊層次收斂是後续改善項目；目前測試不構成所有失敗狀態的視覺驗收。

## 追加：失敗狀態 UI 回歸

## 追加：歷史來源保留保護

- 發現 upload API 與舊 Worker 都會呼叫 cleanup_expired，僅按資料夾 mtime 刪除，未查 Task/Run 引用。現階段集中停用該刪除行為，回傳 0，不刪任何檔案。
- retention_days／expires_at 暫時僅為保留政策 metadata，不保證到期刪除。需補上引用檢查、預覽及清理驗收；磁碟用量可能持續增加。舊檔若先前已被刪除，本次修正不會恢復。
- 39 項本機測試通過，包括 90 天舊目錄與新上傳共存、清理不建立不存在的目錄。部署後真實上傳流程再次通過（7.5 秒）：TASK-20260913-0114，Run 6c47ab55-cf10-4f9c-8426-07a70f46bfb5。
- 沒有新增模型或 ETL 寫入；原先預定的同 Task 換檔修訂仍待完成。

- source-evidence.spec.ts 通過（1.6 秒），以合成 Run API 回應檢查無證據、缺檔、內容異動、缺少版本綁定、非法檔案、未知狀態、CSV 標題不符與資料缺欄位。
- 確認失敗狀態不顯示完整性成功或 CSV 通過；標題列與資料記錄號分開呈現，390px 無水平溢出、無 pageerror。
- 此為 UI 分支驗證，不是新增真實來源／PostgreSQL Gate 或 ETL 驗收。測試在控制資料庫建立一個合成 Project/Task，Run 回應僅在瀏覽器攔截，沒有派發模型、Worker 或執行 ETL 資料寫入。
