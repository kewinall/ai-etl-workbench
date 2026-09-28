# Excel V4 規格、角色證據與編譯驗證（2026-09-28）

狀態：已接通純規格／角色輸出驗證與 HPL/HWF 候選編譯，
**尚未接通正式派發、Vertica QA 與 Release，未部署為完整 Excel 執行能力**。

## 實作與保護

- `EtlSpecificationV4` 使用單一原生 XLSX，沿用已確認 Filter、Aggregation、Projection
  與 APPEND 語意；以內容、profile 及讀取契約三個 checksum 綁定 `excel_source`。
  不將原 V1／V2／V3 換成新格式，不用 CSV 轉檔冒充 Excel。
- `validated_excel_contract` 核對單一已上傳 Excel、profile 完整內容與 checksum、
  工作表、標頭、欄位及契約；混用 CSV 契約或不完整來源即拒絕。
- Requirement Gate 缺少／衝突讀取契約時要求補正。Worker 若有契約，對已核對的同一
  bytes 做完整結構／型別掃描；後續資料型別錯誤也會成為來源衝突，不能由 SA 覆蓋。
- SA context V5 增加白名單 `source.0.excel_input` 證據，不含 upload ID、路徑或樣本。
  READY_FOR_REVIEW 必須引用此證據；這不是實際模型呼叫已驗收的聲明。
- Developer context／proposal V4 使用對應 JSON Schema；專用 prompt version 7 要求
  精確複製來源指紋並引用 Excel 證據。少引用、改指紋或使用舊版規格均拒絕。
- HPL 為原生 ExcelInput；HPL/HWF 都宣告 `SOURCE_XLSX`，不夾帶實體路徑／資料。
  候選編譯永遠回報 `execution_authorized=false`。

## 可重現證據

- 本機針對性回歸 **28 passed / 1.41s**，包含缺漏、篡改、政策變更、證據引用、
  schema/prompt 一致性、Worker 全檔檢查及 CSV 相容性。
- 相容性測試直接取 Git 固定基準 `25120fc520cd14d01004e20aa9a8a1718fe3ddc5` 的實作，
  對同一輸入比較 V1 單 CSV、V2 Join、V3 來源順序的完整 SA context、HPL、HWF、
  規格／計畫／產物 checksum，三版本全部一致；不是只比目前實作自身的重複輸出。
- 真實 Hop **10 passed / 51.76s**。新增 V4 完整 compiler 的
  `ExcelInput → FilterRows → SortRows → GroupBy → SelectValues`，只將 DB sink 換成
  記憶體 collector。四筆輸入篩選後，A=150.25／1 筆、B=500.50／2 筆，精確符合答案。
  其餘九項原生讀取／型別／staging 回歸也通過。
- HWF 本次驗證参数與 HPL 一致，未聲稱 workflow 真實派發與 DB 寫入已驗收。
- 全後端隔離回歸 **1586 passed, 95 skipped, 1 warning**。略過不算通過；native 及
  Git 基準相容性依上列另外執行。既有 Starlette／AnyIO alias warning 未在本輪處理。

本輪無真實模型用量、無正式 Task／DB／release mutation、無 migration；測試使用隔離
PostgreSQL 及無網路 Hop。後端測試完成自動停止，volume 保留。

## 下一步與未完成

1. 接入 Excel 讀取契約確認／補正 API 與網站，建立新 revision 並讓舊下游核准失效；
   同步 SA Excel 專用提示的版本化與持久化引用，做真實角色驗收。
2. 將 `stage_excel_source` 接入 `execution_preparation`，接通原生 launcher 的
   `SOURCE_XLSX`、metadata／runtime options／QA 證據；保持原子授權與不明結果禁重跑。
3. 真實 Run → Hop → Vertica → QA → SDM → portable ZIP 完整驗收，包含正式網站操作。
4. JSON、資料表與受控範例表重建等原規劃範圍仍未完成；不能由這份證據取代。

人工基準維持未量測。整體目標未完成。**尚未持久化至 knowledge-workspace**；
有權限的接續工作應更新 WS-0007，引用本證據及上述 next action。
