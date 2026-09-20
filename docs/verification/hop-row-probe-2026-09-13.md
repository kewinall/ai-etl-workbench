# 原生 Hop 合成資料列驗證

2026-09-13 已把合成 CSV bytes 預檢、規格驅動 HPL 編譯、原生 metadata 檢查及 LocalPipelineEngine 實際列處理串成可重現測試。這不是模型 mock；資料處理使用本機 `apache/hop:2.12.0`。但它不是平台 UI→Worker→Vertica→Release E2E。

## 重現與證據

repo 根目錄：`./scripts/test-hop-compiler.ps1`

- 46 項規格／編譯測試通過。
- CSV 預檢成功，7 筆；bytes SHA-256 `fcdf87c47b7ae37e3d581fe21ba3100ca3adb0063a41ff6897f0c10ef76c477f`。
- 本次 HPL SHA-256 `614d6f02944f71083b6af8ddc915423adbeb945d4994a03fed8330354de8be64`。測試 Run UUID 每次不同，checksum 因版本識別不同而改變。
- 原生 metadata：7 transforms／6 hops，3 個投影欄位及型別一致。
- Hop CSVInput 寫出 7 筆；discard 收到 3 筆；sort 收到 4 筆；aggregate／projection／測試 collector 各輸出 3 筆；全部 E=0。
- 最後一次引擎 log duration 0.151 秒，不含 JVM／容器啟動，不能當作平台整體耗時或商業成效。

標準答案：

| category | total_amount | row_count |
|---|---:|---:|
| A | 301.35 | 2 |
| B | 300 | 1 |
| a | 110 | 1 |

驗證金額 >100（100 被排除）、空金額被排除、十進位 101.25+200.10、COUNT_ROWS、大小寫分組不合併。Java collector 將金額以 BigDecimal 比對，不用浮點容差掩蓋差異。

## 測試邊界

`ExecuteCompilerProbe.java` 僅接受固定 fixture 路徑、不接受外部參數。測試在記憶體中將 TableOutput 替換成 Dummy + RowListener；原始 HPL 檔案不改寫，其他處理節點保留。此替換只用於切開資料處理與資料庫問題，不是產品替代方案：Vertica 仍為目標引擎的必要驗收。

容器無網路、唯讀掛載合成 fixture 與候選；沒有資料庫憑證。未修改平台執行旗標、未追加 Copilot 呼叫。新增的工具沒有在 API／Worker 暴露任意 HPL 執行入口。

## 尚未驗證

- 實際 TableOutput、連線、DDL、Vertica 寫入／型別／transaction／重跑界線。
- 全 null 聚合、所有 Filter operator、Big5／BOM／extra columns 等完整 parser 等價矩陣。
- 平台來源 bytes 的不可變持久化／預檢後變更防護；本測試的唯讀掛載不是該機制。
- 規格版本核准、HWF、UI／Worker 接線、QA evidence 持久化、SDM／Release ZIP。
- P2 四情境、P3 20 案例及人工基準。P0–P3 仍未達標。
