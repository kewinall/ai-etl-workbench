# 複雜 ETL 試跑資料

來源檔案：`sales_orders.csv`

流程：

1. 讀取 CSV。
2. 依平台驗證政策取前 10 筆。
3. 計算 `line_amount = unit_price × quantity`。
4. 依 `category` 排序。
5. 依 `category` 分組，加總 `line_amount` 為 `total_amount`。
6. 寫入 PostgreSQL `poc_validation.complex_sales_summary_20260812`。

前 10 筆資料的預期結果：

| category | total_amount |
|---|---:|
| Cloud | 21,000 |
| Hardware | 23,150 |
| Service | 19,800 |
| Software | 17,500 |

第 11、12 筆不會納入，藉此驗證平台的 `FIRST_10_VALID_ROWS` 政策。
