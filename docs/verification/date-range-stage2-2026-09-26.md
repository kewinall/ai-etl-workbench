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

## Pilot 新案例準備

已從 92309fa 重建 API／網站，恢復既有 Pilot PostgreSQL、API、網站及
Control Worker；未刪除 volume、未啟動模型或 Hop 派送。網站與 ready API
可讀取，瀏覽器可開啟新 Task 的六頁籤工作區；這不是完整 UI 回歸。

- Project：`e45e0cab-7913-4bc0-8a53-ccb2dabfc8ff`
- Task：`TASK-20260926-0001`
- 待輸入核准 Run：`0d958087-b8a3-40e3-9523-49c8f62d8ce7`
- 原始需求使用「最近客戶」，刻意未指定期間，準備測試 Gate 補正。
- 來源為六筆合成 CSV；自動 profile 為 category VARCHAR(32)、amount
  DECIMAL(18,4)、event_date DATE。
- 來源 SHA-256：`4ae1b9e0a1743856143ae9207b1c919b600a27d37f3e16322f0218ef5eeea9c7`
- 既有 Copilot Profile 三角色皆解析為 `copilot/gpt-5.4`，沒有切換模型。
- Copilot CLI 安裝版本 1.0.83；版本查詢不是模型連線驗收。

待使用者確認補正為 2026-09-01（含）至 2026-10-01（不含），空日期排除，
依 category 彙總 amount 與筆數，APPEND 到新的 `ai_sample.pilot_date_range_20260926`。
獨立標準答案應為 A=150.2500／2 筆、B=200.0000／1 筆；尚未實際執行，
不可將預期答案記為實測結果。此表尚未由本次流程建立或寫入。
待核准不是服務或程式故障，也不代表階段 2 完成。

## Developer 日期交接補強

Developer prompt 升為 v2，明確說明 RANGE 的 GE／LT DATE 常數、命名對應、
空日期排除及無時區 TIMESTAMP 午夜界線；不再要求模型自行推測編譯器限制。
context 仍傳遞已確認的 conditions，不變更既有 context/schema 版本。
歷史呼叫保存原 prompt 與版本，不覆寫既有 Release 紀錄。

- 定向 Developer／本機 Worker 測試：19 passed（0.52 秒）。
- 完整隔離回歸：865 passed、25 skipped、1 warning（20.76 秒），exit 0。
- API 映像已重建並更新；未啟用模型或 Hop 派送。
- 本輪沒有真實模型呼叫；待使用者確認日期案例的狀態不變。

## 18:10 實際日期補正與 SA 結果（優先於上述準備狀態）

使用者確認日期規則後，原始 Run 經輸入核准，真實 Control Worker 回傳
NEEDS_INPUT，指出 requirements_v1.date_scope 為 AMBIGUOUS；六筆來源 bytes
驗證成功。補正版 `693d61a1-f0fb-45d8-8b19-c549fd6dd36f` 建立後重新輸入核准，
Gate 為 CHECKED。父 Run 與缺口保留，不重用舊核准。

對子 Run 進行一次真實 `copilot/gpt-5.4` SA：

- Invocation：`0044f4a2-f727-4bd5-800b-580f7f530315`
- 結構驗證：VALIDATED_NOT_APPROVED；語意結果：**NEEDS_INPUT**。
- 時間：22,937 ms；6.43975 AI credits、1 premium request、1 CLI session。
- 自動重試 0、工具操作 0；token 數未提供，不當作零。
- 缺口一：明確定義目標輸出欄位、型別與對應。
- 缺口二：category／amount 空值處理未指定。

日期範圍已被模型正確理解；沒有將模型缺口改成 PASS 或人工核准，沒有
Developer／Hop／Vertica 寫入。下一步請使用者確認輸出 category VARCHAR(32)、
total_amount NUMERIC(24,4)、row_count BIGINT；並決定 category／amount 空值規則，
再建立新 revision 重跑 Gate／SA。正式 Release 不在本次確認範圍內。
