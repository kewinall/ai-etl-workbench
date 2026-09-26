# 階段 2：日期需求補正（部分驗證）

目前不是階段 2 完成，也不是新的正式 Release。

## 修改

- 日期條件不再一律拒絕編譯：RANGE 必須對應 Naming Contract 中的 DATE／TIMESTAMP 欄位。
- 必須恰有 `>= start_date` 與 `< end_date_exclusive` 兩個 DATE 常數條件；漏值、改值、重複、額外同欄位條件及字串比較都拒絕。
- TIMESTAMP 使用 CSV 的本地無時區時間與午夜日期界線，不推定任何時區轉換。
- 保留版本、checksum、人工核准與來源欄位編輯保護。

## 本次實測

隔離 `ai-etl-locked-regression`，`deploy/compose.p0-tests.yml`：
**863 passed、25 skipped、1 warning，20.61 秒，exit 0**。
沒有模型請求或 Vertica 寫入；結束後測試容器正常停止、volume 保留。

新 PostgreSQL 整合測試驗證：

1. 「最近客戶」缺少期間，Gate 回傳 NEEDS_INPUT。
2. 補正期間產生不同 checksum 的子 revision，重複請求維持相同子 run。
3. 未重新核准不會執行；使用父版本 checksum 核准遭拒。
4. 正確核准後重新執行 Gate；保留父版本輸入與缺口紀錄，不啟動 ETL 寫入。

首次新增測試曾失敗：錯把需求補正與受保護的檔案 metadata 修改合併。
修正 fixture，日期欄位在原始來源即存在；沒有放寬 production 保護規則。

DATE／TIMESTAMP 原生 Hop 邊界測試另以禁網容器執行：2 passed，7.08 秒，exit 0；各五筆合成資料，
起日前、起日、迄日前、迄日、空值；輸出 2 筆、排除 3 筆。
此測試使用 Dummy 取代 TableOutput，只證明 Hop 邊界處理與筆數，
不代表 Vertica 逐筆 oracle 比對或同 Run 模型驗收。標準回歸中的 25 個跳過項目
包含這兩個需另行啟用的原生測試；其餘原生／既有證據測試不是本輪完整重驗。

## 下一步

建立新的隔離日期案例，補正後以同一子 Run 完成真實模型、Hop、Vertica
逐筆標準答案與 QA 證據鏈；不得重跑已核准的 TASK-20260917-0007。
完成前階段 2 保持進行中；階段 3–7 尚未完成。
