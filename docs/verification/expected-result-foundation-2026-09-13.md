# 標準答案比對基礎（未接正式 QA）

## 後續原生 Hop 驗證

test_source_staging_hop.py 已接入共用比對器：Hop 2.12 實際執行固定 CSV → Filter／Aggregation，測試收集器輸出 A/301.35/2、B/300/1、a/110/1，再由 Python 精確多重集合比對。1 passed，5.88 秒。另將實際結果的 A 合計加 1，筆數不變仍判定 MISMATCH。

測試容器 network=none，目標 TableOutput 僅在測試中換成 Dummy 收集器；不是 Vertica 寫入或正式 Worker QA。Java 只輸出此固定合成 fixture 的三筆資料，非一般生產資料 Log。原來源異動後暫存來源仍固定、暫存完成後清理的既有斷言保留。

比對器另已加入每側 8 MiB 標準化 JSON 內容預算（含重複列與 Unicode 展開），相關本機測試共 19 項通過。此上限不等於資料庫擷取層的記憶體／查詢限制；上游仍須限量擷取。

新增 expected_result.compare_expected_result，接受明確欄位定義與 expected/actual 列。採無序多重集合比對，重複列的次數必須一致；不僅比較總筆數。

支援 TEXT／INTEGER／DECIMAL／BOOLEAN 與明確 nullable。文字大小寫及空白不自動修正，null 不等同空字串；型別不隱式轉換，浮點數不能當作精確 DECIMAL。Decimal 字串化不依賴目前 context precision，避免 normalize 導致四捨五入。

證據只含筆數、缺少／多出數量、欄位與結果指紋，不含原始列。MATCH 不代表執行成功，qa_passed/release_ready 固定 false。空對空也不能授予交付。

本機 16 項單元測試通過（0.04 秒）：亂序、重複列、同筆數不同內容、低 Decimal precision、null／空字串、文字、無效型別與欄位、不接受未限制的 iterator。

限制：尚未查詢 Vertica、保存標準答案版本、綁定 Run/checksum 或納入 QA evidence；日期／時間與浮點容差政策未支援。每次最多 10,000 列、128 欄，仍須由未來資料擷取層限制整體位元組與查詢資源。未部署或接入 API，不是四案例真實驗收。
