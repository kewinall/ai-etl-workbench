# Module Pipeline ETL 試跑

主 Pipeline：

`CSVInput → FilterRows → SimpleMapping → SortRows → GroupBy → TableOutput`

計算 Module Pipeline：

`MappingInput → Calculator → MappingOutput`

Module 計算：`movement_amount = unit_cost × quantity`。

主流程使用前 10 筆有效資料，呼叫 Module 計算每筆異動金額，再依 `item_group` 分組加總成 `total_amount`，寫入 `poc_validation.module_inventory_summary_20260812`。

預期結果：

| item_group | total_amount |
|---|---:|
| Network | 279,000 |
| Server | 654,000 |
| Storage | 286,000 |

預期總額：1,219,000。第 11、12 筆不納入 `FIRST_10_VALID_ROWS` 試跑。
