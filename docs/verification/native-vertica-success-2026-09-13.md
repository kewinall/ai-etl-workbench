# 原生 Hop → Vertica 首次結果一致驗證

## 已驗證

- 使用平台 PostgreSQL 保存的連線及指定版本加密密碼；非環境預設連線。
- Hop 2.12.0、Vertica JDBC 25.3.0-2、Vertica 25.3.0-2。
- 平台編譯器原始 TableOutput 未替換為 Dummy；經 Run 輸入／規格／標準答案核准、單次 reservation 與 write gate 執行。
- 合成 CSV：A 101.25、A 200.10、B 99.00；Filter amount > 100，依 category 加總及計數。
- runner 核對成功後，另一次獨立連線確認資料為 A、301.35、2。
- Run：65269428-7e6c-434b-a16e-5d557608f184；Task：native-pilot-cfa3b2c957224122977a74db48b0ed0b。
- Project：d16a1663-597c-4c63-930e-d3350cee3140；測試表 ai_sample.pilot_cfa3b2c957224122977a74db48b0ed0b 保留，無 DROP。
- Run 狀態 NEEDS_REVIEW、HOP_EXECUTED_QA_REQUIRED，write_started=true，lease 已釋放。
- 私有 Hop Log SHA256：3ece3abe518fc03e916af4e8110df5ed6dbf1c5dd67f6c876467479262ab7280。

## 發現與修正

先前三次失敗皆保留。最初 VERTICA 插件要求舊 com.vertica.Driver；改用原生列舉確認的 VERTICA5，匹配 com.vertica.jdbc.Driver。固定共享 JDBC 目錄已傳入。一般環境密碼參照未解析；受控 Java launcher 改在 JVM 內設定 property，密碼不放 argv 或 metadata。

## 後續結果查詢驗證

- 從 PostgreSQL 中本 Run 的 execution authorization、specification、Naming Contract 重建結果查詢；與執行前核准的 query checksum 比對一致。
- 查詢 checksum：e02064082acba6333a0b07a1dbac2085418955eebc98f05ea4e90a58667359cd。
- 使用 Run 設定快照及指定版本的加密機密重新連線，只執行編譯器的完整目標投影查詢，未重跑 Hop、未修改 Vertica 資料。
- EXACT_MULTISET：MATCH；expected=1、actual=1、missing=0、unexpected=0。
- PostgreSQL comparison ID：0791358f-f800-4772-8567-dd3e70b129ce。與先前相同比對共用同一紀錄，沒有重複新增。
- 查詢身分與連線版本已核對；exclusive target ownership 尚未完整實作，故 actual_provenance 仍為 NOT_VERIFIED，qa_passed/release_ready 仍 false。
- 本次以 worker 容器掛載目前原始碼驗證，不代表正式網站入口已接通。

## 尚未完成

本案例由內部 opt-in runner 執行，AI Profile 為明確合成設定、未呼叫模型；不是 SA/Developer/QA 完整協作。正式 API 與常駐 Worker 的執行開關仍關閉。尚需正式結果來源綁定、QA 證據核准、同 Run SDM／Release 與網站實跑驗收。P1、P2、P3 均未完成。
