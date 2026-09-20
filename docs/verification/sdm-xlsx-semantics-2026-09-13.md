# SDM 儲存格內容比對

新增 sdm_xlsx_semantics.py：從有效 Specification／Run／Naming 重新建立目前候選版面的預期儲存格，再讀取 XLSX 的兩頁實際文字／數字進行精確比對。輸出欄位、順序、型別、來源原名、目標表、篩選與版本指紋均納入；多餘非空白儲存格也拒絕。

先通過有大小限制的結構檢查，再解析 shared string、inline string、純文字 str 與數字。拒絕越界／重複座標、無效字串索引、不支援型別與非有限數字。沒有執行公式或讀取外部連結。

build_checked_bundle_candidate 已改為呼叫語意檢查，不只檢查 SDM 結構。這是程式碼整合，尚未部署或開放下載。

## 驗證

- 結構／語意／候選封裝：40 passed（0.25 秒）。錯誤欄位、型別、來源、順序、目標、指紋與額外資料均被拒絕。
- 初次實際 XLSX 回讀失敗：renderer 使用 t=str 儲存純文字，解析器原先未支援。加入該分支後重跑成功，公式仍由結構檢查拒絕。
- 原合成 Excel 的 Run/Naming 識別碼讀回作為 fixture 身分，業務規格仍使用原 design() 定義，不從工作簿反推欄位、型別或條件。結果 CANDIDATE_LAYOUT_MATCHED，原檔 SHA-256 不變：cb52844ed01573550ec24bbca9d7192be9abd89c6437cc992d71244b75ba3955。
- 未重新匯出 Excel、未使用模型或資料庫。

## 限制

比對目前固定版面的語意，不是完整 OOXML／Excel native application 驗證。renderer 與 Python 預期版面分處兩種語言，後續仍需共用版面契約與跨實作回歸，避免漂移；聚合 NULL 政策文字也尚待補入版面。樣式、未使用 shared strings／XML 擴充中的額外文字、機密與主機資訊仍須可攜性檢查。

狀態仍為候選、portability=NOT_VERIFIED、qa_passed=false、release_ready=false。正式 renderer 部署、權威 artifact 核准與保存、真實 Vertica QA 及 Release 尚未完成，P0–P3 目標未達成。

## 後續額外內容檢查

補上未引用 shared strings、孤立 cell、重複 row、cell 與 row 座標不一致、重複 sheetData 的拒絕。只看已解析儲存格可能漏掉檔內額外文字，現在要求字串表每個索引都被使用，且所有 cell 均屬於唯一 sheetData 的合法 row。

- 結構／語意／封裝 45 passed（0.25 秒），新增 5 個額外內容或歧義結構案例。
- 原 renderer 的實際 XLSX 再次通過，指紋保持 cb52844ed01573550ec24bbca9d7192be9abd89c6437cc992d71244b75ba3955；未重新匯出或修改檔案。
- 此修正尚未部署。其他 XML 擴充／樣式屬性等尚未做完整可攜性檢查，不宣稱已排除所有資料外洩方式。
