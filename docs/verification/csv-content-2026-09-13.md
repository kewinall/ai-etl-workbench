# CSV 原始內容預檢

新增 `backend/app/csv_content_validation.py`，直接驗證傳入 bytes，不讀取任意檔案路徑、不改寫資料、不執行 ETL。

2026-09-13：CSV 內容預檢 14 項測試、既有規格／HPL 編譯 46 項測試，共 60 項通過。

涵蓋 UTF-8／UTF-8-SIG／Big5 嚴格解碼、BOM 與契約不符、精確標題順序、重複標題、缺少欄位、REJECT 額外欄位、IGNORE 尾端額外欄位、引號與跨行欄位、空資料、NUL、解析錯誤、bytes／筆數／問題數上限。IGNORE 不允許缺欄或重新排列必要欄位。

成功回傳 `CSV_STRUCTURE_VALIDATED_NOT_EXECUTABLE`，包含 bytes／契約／來源欄位 checksum、筆數、額外欄位筆數與完整掃描旗標。失敗只回傳代碼及邏輯紀錄序號，不回傳 cell/header 值或 exception text。最多 50 MiB、100 萬筆、20 個問題；達上限不得把部分掃描標示為成功。

重現（backend 目錄）：

```powershell
../.venv/Scripts/python.exe -m pytest tests/test_csv_content_validation.py tests/test_hpl_compiler.py tests/test_etl_specification.py -q
```

## 尚待接線與驗收

- 目前為獨立內容預檢模組，未接入上傳、API 或 Worker，網站尚無新增功能。
- 使用 Python csv strict Excel dialect 做結構檢查，不是 ETL engine。與 Hop 的 quoting、BOM、空值、日期、型別及額外欄位處理一致性仍須實際執行比對。
- 不驗證欄位值的宣告型別或業務語意；結構合格不代表資料可正確轉型。
- 必須將此證據綁定同一次執行的不可變來源 bytes，避免預檢後檔案被替換。尚未有該 Worker 接線，不能解除 HPL 候選的禁止執行狀態。
- 未呼叫模型、連線 Vertica 或改動現有平台服務。P0–P3 仍未完整達標。
