# JSON 重播 Worker 與原生 HWF（2026-09-28）

本階段已接通 Worker JSON 分支，未部署正式或完成真實 Vertica／ZIP E2E。

- 重播使用 stage_json_source，不回退 CSV；啟動固定 SOURCE_JSON 與 HOP_JSON_INPUT_INCLUDE_NULLS=Y。
- 在建立目標之前、引擎完成之後核對原檔與 BOM 讀取副本的大小、指紋、非符號連結及暫存證據。
- 來源授權不符在重播領取前拒絕；執行後保留私人 log，receipt 必須唯一且綁定實際 log 指紋。
- V5 證據沿用獨立目標、標準答案、產物完整性與原流程核准檢查；異常不自動重試、不核准 Release。

驗證結果：

- 30 項編排／檔案／證據正反例通過；其中 DB 與引擎為明示假物件，不算 E2E。
- 完整隔離後端 1994 passed、135 skipped、1 warning（52.16 秒）。
- 隨後擴充原生測試，8 passed（37.82 秒）：HPL／HWF、一般／私有 launcher、正常／缺檔；真正 Hop 在 --network none 容器執行，目標改為 Dummy。
- 原生正常案例保留 6 筆來源（包含空物件）、輸出 2 筆聚合；HWF 完成紀錄與缺檔失敗均符合預期，私有 launcher receipt 與節點 metrics 通過。

原生測試只替换測試目標，不聲稱未改動交付物的 Vertica 重播已通過。沒有正式部署、模型呼叫、原 Task 重跑或既有資料刪除。

下一步：為缺 receipt／重播途中改檔補編排負例，驗證最終 ZIP／SDM 視覺與資料排除規則；重建 API、Worker、Web 後以新 JSON 案例完成真實模型、Hop、Vertica、QA、可攜重播及正式 Release。第 5–7 階段仍未完成，人工基準未量測，knowledge-workspace 尚未持久化。
