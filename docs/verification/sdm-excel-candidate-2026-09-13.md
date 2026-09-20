# SDM Excel 候選產生器

新增 scripts/sdm/render-candidate.mjs，從 stdin 接收 build_sdm_candidate 的 JSON，使用本機 bundled @oai/artifact-tool 產生兩頁 XLSX。此為開發產物工具，不是已部署的後端功能，沒有將 Codex 文件 runtime 當成平台依賴加入。

## 已驗證

- 合成 Specification 產生 outputs/sdm-render-20260913-01/SDM-candidate.xlsx，5,618 bytes。
- 「欄位對照」：category、total_amount、row_count，中文原名、型別、轉換方式及來源英文欄位。
- 「規則及版本」：來源、目標、APPEND、篩選、分組、Run、Naming 與 Specification/SDM 指紋。
- 使用試算表技能，略過不相符的通用範本；兩頁實際渲染並人工視覺檢查，中文、數字、指紋可讀，未見裁切。候選／未 QA／不可交付提示可見。
- Node 內建測試 4 passed（59.2ms）：不修改輸入、公式樣式文字加 literal 前綴、指紋／狀態不符拒絕、超長與非法控制字元拒絕。
- bundled Python/openpyxl 僅用於唯讀重開儲存檔：兩頁名稱、total_amount／NUMERIC(18,2)、無公式 cell、兩頁 freeze_panes=A6 均符合。
- 不覆寫既有輸出；renderer 遇到同目錄既有候選或圖片會拒絕。來源資料與連線不進文件。

## 開發環境使用

使用 load_workspace_dependencies 提供的 Node 與 @oai/artifact-tool。將 WORKBENCH_ARTIFACT_NODE_MODULES 設為 bundled node_modules 目錄，以已驗證候選 JSON 經 stdin 傳入：

```text
node scripts/sdm/render-candidate.mjs <新的輸出目錄>
node --test scripts/sdm/render-candidate.test.mjs
```

第一個命令必須提供 stdin JSON；不自行查詢 DB、要求模型或載入平台機密。輸出目錄應保持空白且不指向歷史 SDM。

## 限制與下一步

此候選不是正式 Release，沒有 QA 或人工交付核准。尚未接入平台 API、下載與不可變 artifact 保存；平台容器未配置此作者 runtime，因此不能宣稱平台已能產生 Excel。正式部署需決定可維護的 renderer 依賴方案。

尚待補全聚合 NULL 政策文字、較長／較多欄位版面、公式樣式文字的實際匯出回讀、XLSX 可攜性／外部關係檢查、完整 schema 驗證與 SDM 封裝一致性。Node 格式模型測試不等於 Excel native application 驗收。沒有執行模型、Hop 或 Vertica。P0–P3 完整目標未達成。
