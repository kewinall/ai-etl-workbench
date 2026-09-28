# JSON 執行綁定與原生啟動驗證

## 判定與限制

已接通 JSON 的準備、單次執行授權、原始／讀取副本驗證及完成後 oracle 綁定。
本次驗證包含原生 Hop CLI，但輸出為 Dummy；資料庫整合使用合成 executor。
**不是 JSON 真實模型／Vertica／QA／SDM／Release E2E 驗收。**
未部署正式 API／Worker，未重跑或修改既有正式交付；第 5–7 階段保持未完成。

## 實作

- `hop-single-attempt-v5` 將原始內容指紋、JSON profile／policy 指紋、讀取副本指紋、
  原始／副本位元組數、BOM-only 正規化方式一起綁定。
- 授權只接受實際受管 upload；重新核對全檔 profile／型別，不信任任意路徑或只有編譯用 fixture。
- 私有 attempt 同時保存 `source-original.json` 與 `source.json`，不改原始 upload。
  最後使用前核對兩份檔案、大小、指紋及「僅移除開頭 UTF-8 BOM」的精確位元組關係。
- 再次核對上游核准；reserve／begin_external_write 都要求完整 binding，拒絕副本變更、
  降版或重複消耗授權。完成後仍可核對綁定的標準答案，不產生第二次寫入權限。
- JSON 啟動固定 `SOURCE_JSON` 與 `-DHOP_JSON_INPUT_INCLUDE_NULLS=Y`，沒有 CSV fallback。
- 正式 adapter 的 JSON 路徑必須用私有 launcher。Launcher 只輸出無資料／無密鑰的
  `WORKBENCH_JSON_READER_V1 INCLUDE_NULLS=Y` 收據；正常退出但收據缺失／重複時，
  保存 log 並標 UNKNOWN，不能成功或自動重試。
- 原 CSV／Excel 的啟動參數與核准政策不變。SDM_JSON_NOT_READY 仍保留；QA／交付尚未接通。

## 驗證

| 項目 | 結果 | 證據範圍 |
|---|---|---|
| 最終針對性測試 | 119 passed，38.10s | JSON 雙指紋、變更拒絕、檔案關係、收據、既有 Excel／CSV 及發行檢查 |
| 其中原生 JSON CLI | 4 passed | 有／無私有 launcher，各有正常及缺檔案例；無網路、Dummy sink |
| 其中原生 Excel CLI | 4 passed | 同一新 launcher 的相容性正反例；未連 Vertica |
| 最終隔離 PostgreSQL 全套 | 1898 passed、135 skipped、1 warning，53.77s | 真實控制 DB，未呼叫模型；跳過不算通過 |

JSON 原生成功案例證明 6 筆輸入（包含空物件）均通過 reader／projection；
篩選丟棄 3 筆，聚合後 target 接收 2 筆。私有 launcher 的最終 9 節點計數完整，
設定收據唯一且正確。缺檔明確非零退出，不能靜默當作零筆成功。

PostgreSQL 案例涵蓋補正核准後準備、取消時拒絕及清除 attempt、副本 binding 錯誤不消耗授權、
授權只能 reserve 一次、最後寫入閘拒絕異動、合成完成後標準答案仍可取回且不能重播。
合成 executor 不代表真實資料庫 side effect 或 Hop 成功。

測試入口：`test_json_execution_binding.py`、`test_json_preparation_integration.py`、
`test_json_runtime_evidence.py`、`test_json_hop_cli_native.py`。
原生測試採唯讀掛載本輪 launcher，因此正式 Worker 映像**尚未**具有此程式；
後續正式部署必須連同 Worker 重建，不能僅更新 API 後直接寫入 JSON。

本輪底層映像：Worker `sha256:7b77c3c713555edca105139f53ad09ba887f8f0f54ec09b77a79a07e06cb5328`；
Apache Hop `sha256:bb744696a831ebf5418fc5350975b6dab787a47cb0b4f9b5cbdce247ba843887`。

## 下一步

1. QA 專用 JSON 結構證據、三個來源節點的獨立 options 檢查與已保存啟動收據引用；不借用 CSV 證據。
2. JSON SDM、可攜包與獨立重播，接完後新增合成真實模型／Hop／Vertica 驗收案。
3. 全鏈通過才開放正式交付；保留原始 20 案分母及人工基準未量測。

knowledge-workspace 的 WS-0007 尚未持久化最新狀態；本專案索引是本輪證據入口。
