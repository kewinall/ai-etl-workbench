# Excel 原生讀取元件驗證（2026-09-28）

狀態：獨立契約、結構檢查及原生 ExcelInput fragment 已實作並測試。
**尚未接入正式受控 Run，未部署為完整 Excel 執行能力。**

## 範圍與證據

- `ExcelInputContractV1` 明示 POI、工作表、標頭列、空白列策略、NULL、
  不修剪字串、拒絕公式／額外欄位及錯誤即停止；未知欄位與非整數版本拒絕。
- 全選定工作表結構檢查使用原始 XLSX，不使用公式快取值代替公式。
  掃描超過上限即拒絕，成功結果仍標記型別轉換未驗證、無執行授權。
- Compiler 只產生 ExcelInput fragment；不生成任意 SQL，不呼叫模型，
  不建立 DB／Release，不改動既有 V1–V3 specification 或歷史 checksum。
- 依實際 worker 內 ExcelInput metadata 核對序列化格式。首次原生測試
  因錯用 `files/file` 包裝讀出零筆，雖 Hop errors=0，資料列比對仍失敗。
  正確格式是 transform 下的 `file`，修正後重跑通過。
- 原生 Hop 使用無網路容器與唯讀合成 XLSX。第二張工作表、第二列標頭、
  `001` 前導零、文字儲存之 `12345678901234567890.123456` 金額均精確匹配。
  SKIP 輸出兩列；PRESERVE 輸出三列且中間兩欄皆 NULL；沒有 CSV 轉檔。
- 原生測試 **2 passed / 10.81s**。
- 隔離 PostgreSQL 全後端回歸 **1544 passed, 84 skipped, 1 warning / 39.38s**。
  84 skipped 不算通過；上述兩項 native 測試另外明確啟用執行。
  warning 為既有 Starlette／AnyIO deprecated alias。測試結束後隔離服務停止，
  volume 保留；未重啟正式平台、未呼叫模型、未重跑既有 ETL。

官方介面參考：[Apache Hop Excel Input](https://hop.apache.org/manual/latest/pipeline/transforms/excelinput.html)。
最新文件不是已安裝版本的 runtime 證據；本次以實際 plugin metadata 及輸出比對為準。

## 未完成與接續順序

1. 補齊日期、Boolean、數值儲存格精度、字串空白及缺值的原生比對與型別拒絕策略。
   本次精確小數為文字儲存格，不代表 Excel 數值已損失的精度可以復原。
2. 版本化 specification／SA context 引用已確認的 Excel 讀取契約及來源 checksum；
   維持歷史 CSV 規格不變，變更上游使下游核准失效。
3. 受控 staging、準備、執行、QA、SDM、可攜 ZIP 全鏈接通後，另做真實 E2E。
4. JSON、資料表與受控範例重建等原規劃缺口仍須完成，不能以顯示限制代替實作。

人工基準依操作者決定保留未量測；不得以代理工時填入或計算改善率。
本機 `knowledge-workspace` 不存在，**尚未持久化至 knowledge-workspace**；
具備權限的接續工作須更新 WS-0007 的狀態、上述證據連結與第 1–3 項 next action。
