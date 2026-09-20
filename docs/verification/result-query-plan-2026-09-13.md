# P1 結果查詢計畫（尚未執行）

## 已確認缺口

execution_result_comparison 接受呼叫者提供的 cursor；comparison_store 明確只接受 actual_provenance=NOT_VERIFIED。內容 MATCH 並不能證明讀到本次 Hop 的目標結果。不可直接把此狀態改成 QA 通過。

## 本輪程式

新增 result_query_plan.build_result_query_plan，在寫入前依既有 compilation_plan 驗證輸入及 Naming Contract，產生固定 SELECT 投影、目標表、SQL checksum、規格／設定／命名 checksum 與完整計畫 checksum。

- 只選輸出欄位，順序及型別與規格一致。
- 不重套來源 WHERE，不 DISTINCT、不再聚合、不用預期筆數限制，避免掩蓋錯誤與重複資料。
- LIMIT 10001 是偵測超過既有 10000 筆驗收上限的哨兵，不是可通過的抽樣結果。reader 收到第 10001 筆必須拒絕。
- 不加 ORDER BY：比對為 EXACT_MULTISET，保留重複且忽略順序；超量時不論子集順序一律阻擋。
- 計畫要求 EXCLUSIVE_RUN_TARGET，但目前沒有實作或證明獨占目標。不能拿共享 APPEND 表的全部資料當作本次 Run 來源證據。

## 證據及邊界

Vertica 技能依 24.4.x 官方離線文件 LIMIT clause（PDF 第 3638 頁）核對 LIMIT 行為；未確認真實 Vertica runtime 版本、連線或執行。

pytest test_result_query_plan.py + test_result_reader.py：16 passed，0.19 秒。涵蓋確切投影、SQL 注入與任意查詢拒絕、過期輸入、指紋變更，以及既有讀取器邊界。不是 DB 原生整合驗收。

這是內部純函式，未接入 public API、未部署新映像、未開啟查詢或寫入。仍須完成計畫持久綁定、Run 專屬目標註冊與權限、連線版本驗證、查詢 timeout／交易清理及結果證據保存，再進行真正 Hop→Vertica→QA 驗收。P0–P3 尚未完成。
