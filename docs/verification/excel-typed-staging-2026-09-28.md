# Excel 全檔型別與暫存副本驗證（2026-09-28）

狀態：讀取元件及執行前來源準備已驗證，**尚未接入正式 Run／Vertica／Release**。
延續 [原生 fragment 驗證](excel-native-fragment-2026-09-28.md)，未改寫既有 CSV 規格。

## 實作

- 全檔檢查可依確認欄位的型別逐格驗證。拒絕隱含字串轉換、UTF-8 長度超限、
  整數小數／越界、Decimal 精度縮減、非有限數、無效日期與日期精度損失。
  Boolean 接受原生 bool 及已實測的文字 `true`／`false`，不將 0／1 或 yes 視為 bool。
- 數值儲存格超過 15 位有效數字要求改為精確文字來源；不能復原 Excel 已損失精度。
  文字 Decimal 與 BIGINT 則按宣告精度／範圍檢查，不轉成 float。
- 結構證據包含內容、契約 checksum、大小及是否做全檔型別檢查；仍明示無執行授權，
  不以 Python 檢查宣稱這份檔案已經通過 Hop 轉換。
- `stage_excel_source` 必須是已上傳 Excel；確認契約工作表／標頭與 profile 相符，
  單次讀取核對 checksum，再對同一 bytes 驗證 profile 與全檔型別。
  以排他建立、0600 權限、fsync 保存獨立 XLSX 副本並重新核對指紋，不轉 CSV。
  context 結束清除當次副本；不清除或修改原上傳。

## 證據

- 真實 Hop 原生測試 **9 passed / 45.37s**：
  工作表／標頭、空白列 SKIP／PRESERVE、前導零、高精度文字 Decimal、
  DATE 字串、原生 TIMESTAMP、原生與文字 Boolean、字串空白、數值 Decimal、NULL、
  BIGINT 文字正負上下界，以及直接唯讀掛載已核對暫存副本。
- 日期測試容器固定 UTC；不擴大聲稱其他時區、時區轉換或所有 Excel 日期格式已驗收。
- 隔離全後端 **1571 passed, 91 skipped, 1 warning / 42.21s**。
  9 項 native 測試在此略過，另如上實際啟用；其餘略過不算通過。
- 新增回歸：20 筆抽樣後出現錯誤型別不能產生暫存副本；選擇／原檔變更拒絕；
  單次讀取、不隨原檔後續變動、執行器拋錯清理、原檔保留。
- 全部 Hop 探針無網路、無 DB、合成資料；未呼叫模型、未更動正式資料或歷史核准。
  隔離後端測試已停止、保留 volume；未部署尚未接通的執行能力。

## 接續

下一步建立 Excel 版本化 specification 與 Developer 輸出，將讀取契約、選擇及來源
指紋納入 SA／Developer evidence 和核准；再連接 compiler、受控 preparation、
runtime 參數、QA、SDM 與 portable release，保持 V1–V3 的既有 checksum 不變。
目前 `etl_specification`、`developer_contract`、`execution_preparation` 仍明確限定 CSV；
不得僅放寬來源型別檢查而跳過上述連接與實際驗收。

第 5 階段及整體目標仍未完成。人工基準維持未量測，不估算改善率。
**尚未持久化至 knowledge-workspace**；接續有權限時更新 WS-0007，引用本證據與
上述具體 next action，不複製程式碼、原始資料或憑證。
