# Hop Job 生成元件參考

## 資料來源與範圍

- 來源：`D:\ChatGPT\hop_transfer\hop\config\projects\transfer`
- 分析日期：2026-08-12
- Pipeline（`.hpl`）：1,430 個
- Workflow（`.hwf`）：655 個
- Pipeline transform：14,804 個，72 種 type
- Workflow action：4,257 個，22 種 type
- XML 解析錯誤：0
- 完全相同內容：0 組；每個檔案都應視為獨立案例，不可只用檔名判斷範本

這批檔案來自 Pentaho Job／Transformation 轉換後的 Apache Hop 專案。未來產生 Job 時，應優先參考同類來源、目標與處理模式的既有 HPL/HWF，而不是只拼接最小 XML。

## Pipeline 常用元件

### 第一級：生成器應原生支援

| 元件 | 次數 | 主要用途 | 生成注意事項 |
|---|---:|---|---|
| SelectValues | 2,244 | 選欄、改名、型別與欄位順序 | 明確產生欄位 metadata，避免依賴隱含傳遞 |
| TableInput | 1,638 | SQL／資料表讀取 | 連線、變數替換、SQL 與欄位型別必須一致 |
| SortRows | 1,398 | Join、Group、去重前排序 | MergeJoin 前必須依 join key 排序 |
| TableOutput | 1,005 | 寫入資料表 | 明確設定 schema、table、欄位 mapping、batch 與 commit |
| SystemInfo | 842 | ETL 日期、系統時間等欄位 | 系統欄位名稱不可與來源欄位衝突 |
| TextFileOutput | 792 | 文字／CSV 輸出 | 明確設定 encoding、delimiter、header、檔名變數 |
| Dummy | 736 | 分支匯合或流程終點 | 僅在流程語意需要時使用，不作為錯誤掩蓋 |
| MergeJoin | 647 | 已排序資料流 Join | 每個輸入流先 SortRows，明確設定 join type/key |
| FilterRows | 612 | 條件過濾與分支 | 必須建立 true/false hop，條件常數要有正確型別 |
| GetVariable | 589 | 將參數／環境變數轉為欄位 | 變數名稱、預設值、資料型別需同時定義 |
| Formula | 464 | 運算與條件公式 | 公式輸出型別及 null 行為需驗證 |
| Constant | 455 | 建立常數欄位 | 避免用字串代替日期、數值或布林值 |
| TextFileInput2 | 268 | 固定格式文字檔讀取 | encoding、分隔符、欄位長度與錯誤處理必填 |
| ReplaceString | 265 | 字串清理 | 明確標示 regex、整字匹配與 null 行為 |
| Calculator | 193 | 標準數值／日期計算 | 優先於自訂 script，輸出精度需明確 |
| GroupBy | 166 | 排序式彙總 | 輸入先依 group key 排序；大量資料優先使用此元件 |

### 第二級：常見進階模式

| 元件 | 次數 | 建議用途 |
|---|---:|---|
| DataGrid | 234 | 小型對照表、測試資料與固定參數列 |
| SimpleMapping | 162 | 重複邏輯模組化；搭配 MappingInput／MappingOutput |
| ScriptValueMod | 157 | 只有標準元件無法表達時才使用 JavaScript |
| ConcatFields | 139 | 多欄位合併輸出 |
| RowsToResult / RowsFromResult | 130 / 14 | Pipeline 與 Workflow 間傳遞 rows |
| ExcelInput | 123 | Excel 資料輸入 |
| FieldSplitter | 117 | 依 delimiter 拆欄 |
| RegexEval | 109 | 格式辨識與擷取 |
| SwitchCase | 101 | 多分支路由 |
| PipelineExecutor | 99 | 執行子 Pipeline |
| Normaliser / Denormaliser | 90 / 96 | 寬表與長表互轉 |
| MemoryGroupBy | 77 | 小資料量、不需預排序的彙總 |
| SetVariable | 62 | 將結果寫回變數；注意作用域與平行執行 |
| ExecSQL | 58 | Pipeline 內執行 SQL；無 row stream 時可用 |
| Sequence | 49 | 流水號或 surrogate key |
| Unique | 48 | 已排序資料去重 |

### 第三級：範本驅動或人工審查

以下元件數量較少或具外部副作用，生成時應先找相似 HPL 範本，並提高驗證等級：

`JsonInput`、`JsonOutput`、`MetaInject`、`MultiwayMergeJoin`、`AnalyticQuery`、`StreamLookup`、`InsertUpdate`、`ShapeFileReader`、`SSH`、`ExecProcess`、`Validator`、`JavaFilter`、`Append`、`WriteToLog`。

## Workflow 常用元件

| Action | 次數 | 生成建議 |
|---|---:|---|
| PIPELINE | 1,252 | 執行 HPL，優先使用 `${PROJECT_HOME}` 相對路徑並傳遞參數 |
| SQL | 951 | 建表、清理、前後置 SQL；交易與失敗路徑需明確 |
| SPECIAL | 654 | Start 節點；每個 Workflow 應有且通常只有一個 |
| SUCCESS | 630 | 成功終點 |
| WORKFLOW | 352 | 子 Workflow；使用相對路徑、避免循環依賴 |
| SIMPLE_EVAL | 216 | 依結果或變數分支 |
| DUMMY | 126 | 分支匯合或中繼節點 |
| EVAL_TABLE_CONTENT | 34 | 依查詢結果判斷流程 |
| WRITE_TO_LOG | 13 | 關鍵稽核訊息 |
| TRUNCATE_TABLES | 10 | 具破壞性，只能在需求明確且連線／表名已驗證時生成 |

少量且需人工審查的 Action：`CHECK_DB_CONNECTIONS`、`COPY_FILES`、`WRITE_TO_FILE`、`SFTPPUT`、`WAIT_FOR_SQL`、`TABLE_EXISTS`、`SHELL`、`SET_VARIABLES`、`MOVE_FILES`、`ZIP_FILE`、`FILE_EXISTS`。

## 最常見設計模式

### Pipeline

1. `TableInput → SelectValues → TableOutput`
2. `TableInput → SelectValues → TextFileOutput`
3. `TableInput → SortRows → MergeJoin → SelectValues → TableOutput`
4. `TableInput → FilterRows → SelectValues → TableOutput/TextFileOutput`
5. `TableInput → Calculator/Formula → SortRows → GroupBy → TableOutput`
6. `GetVariable + SystemInfo → SelectValues → TableOutput`
7. `DataGrid → RowsToResult`，供 Workflow 或子流程取得固定參數列
8. `TextFileInput2 → 清理/驗證 → TableOutput`

### Workflow

最常見組合為：

1. `SPECIAL → SQL → PIPELINE → SUCCESS`（193 個 Workflow）
2. `SPECIAL → SQL → SUCCESS`（94 個）
3. `SPECIAL → PIPELINE → SUCCESS`（87 個）
4. `SPECIAL → PIPELINE/WORKFLOW → SUCCESS`（68 個）
5. `SPECIAL → SQL → PIPELINE/WORKFLOW → SUCCESS`（65 個）

建議預設骨架為「前置 SQL → 一或多個 Pipeline → 後置檢核 → Success」，並為每個可失敗節點建立清楚的 failure hop。

## 常用參數與連線慣例

最常見參數：

| 參數 | 出現檔案數 | 語意 |
|---|---:|---|
| DATA_YR | 827 | 資料年度 |
| SourcePath | 779 | 來源根目錄 |
| TABLE_NAME | 680 | 動態資料表名 |
| DATA_YQ | 331 | 年季 |
| DATA_YQM | 159 | 年季月 |
| DestTable / DestSchema | 111 / 111 | 目標表與 schema |
| SrcTable / SrcSchema | 101 / 101 | 來源表與 schema |

連線引用以 `M_ETL_0001`（1,455 次）及 `M_ETL_0002`（1,111 次）為主。生成器應引用 Hop metadata connection name，不應把帳號、密碼或 JDBC URL 寫進 HPL/HWF。

## 生成器採用規則

1. 先依「來源型態、目標型態、Join／彙總／輸出需求」檢索相似流程。
2. 優先重用既有元件組合和 XML 欄位結構，不複製業務 SQL、實體表名或敏感資料。
3. 只生成需求用到的元件；高頻不代表每個流程都必須加入。
4. `MergeJoin` 前強制檢查每個輸入是否已依 key 排序。
5. `GroupBy` 前強制排序；只有可證明資料量小時才使用 `MemoryGroupBy`。
6. 優先使用 `Calculator`、`Formula`、`ReplaceString`、`RegexEval` 等標準元件；`ScriptValueMod` 是後備方案。
7. 所有輸入、輸出與參數都要明確指定資料型別、null 行為、encoding 和欄位 mapping。
8. 外部副作用元件（SQL DDL/DML、檔案移動、SFTP、Shell、SSH、Truncate）必須經額外審查。
9. HPL/HWF 路徑一律使用 `${PROJECT_HOME}` 或專案相對路徑，不保留原 Pentaho 主機的絕對路徑。
10. 生成後至少執行 XML、元件存在性、hop 連線、參數、資料型別、路徑安全及 Apache Hop dry-run／小量資料驗證。

## 不應直接學習的內容

- `Archive`、`temp`、`test` 命名路徑可用來理解元件設定，但不應自動選為首選範本。
- 已 URL encode 的檔名不代表建議命名方式。
- 歷史流程中的硬編碼日期、磁碟機路徑、schema/table、連線名和舊系統帳號不可直接帶入新 Job。
- 低頻元件不等於不可用，但需要相似案例與更嚴格驗證。

