# 原生驗證工具的版本控制完整性修正

檢查目前工作目錄發現 `.gitignore` 的 `hop/` 規則同時排除了本機安裝目錄及 `scripts/hop/`。因此 Java 原生驗證器與合成 fixture 雖在本機存在，卻不會出現在一般 Git 新檔清單；僅提交 PowerShell runner 會缺少依賴。

已用精確白名單放行 3 個 Java 原始碼與 5 個合成 fixture，其餘 `scripts/hop/*` 及 fixture 未知檔案仍排除。不放行安裝 jar、任意 CSV、credentials 或生成產物。

驗證結果：

- `test_source_distribution.py` 通過，檢查 10 個必要來源（包含兩個 runner）都存在且未忽略，8 個敏感／runtime／未知路徑仍忽略。使用 NUL 分隔，避免 Windows stdin 換行變換干擾 Git 路徑。
- `git status --untracked-files=all -- scripts/hop` 顯示全部 8 個檔案可追蹤。
- 規格／編譯 46 項測試再次通過；原生 Hop metadata 及資料列測試再次成功（7 筆輸入、4 筆通過 Filter、3 筆聚合輸出、errors=0）。沒有 Vertica target 執行。
- API ready、execution_enabled=false，沒有重啟平台服務或新增模型呼叫。

尚未 commit／push，也沒有宣稱 GitHub 已更新或乾淨 clone 驗收完成；此修正只確保後續正常提交時能看見必要來源。P0–P3 完整交付與乾淨環境重現仍待驗證。
