# 階段 2：日期需求補正（部分驗證）

最新判定：第 2 階段日期案例驗收通過，已產生新的正式 Release。
以下早期段落為歷史紀錄，最新實測與限制見文末。

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

## 19:12 日期案例驗收完成（最新判定）

使用者後續明確授權自動核准並持續完成目標。核准由代理依此授權操作，
不是宣稱使用者逐筆點選網站。程式檢查、版本綁定與禁止重試規則仍保留。

### 版本與真實模型

- 補正版 `57bb0291-efbf-40d2-8abd-f36d86a83c1f`：SA
  `9e928ba5-4bdd-47bc-8a38-e98e1b2f807f` NEEDS_INPUT，要求 CSV 空值／錯誤策略。
- 最終 Run：`105c0171-020d-4230-9ff3-d705cc56c5d8`，技術契約補正後重新核准。
- SA `b98ae107-8861-4c9c-b758-4fa7dfa57d75` READY_FOR_REVIEW；13,250 ms，3.8399 credits。
- Developer `edd28422-68d8-4fe4-b18e-257068f03c71` VALIDATED_NOT_APPROVED；14,531 ms，4.6939 credits。
- QA `f5407d69-06d4-4d50-82be-d18d46f896f2` PASS；27,953 ms，5.99815 credits。
- 全部使用 copilot/gpt-5.4。三次 SA（含前兩次缺口）＋Developer＋QA 共五次模型請求；
  每次一個 CLI session／premium request、零自動重試與工具操作。Token 未提供。
- 第二次 SA 耗時 27,859 ms、5.69265 credits；第一次 SA 證據保留於上節。
- 本次 QA 首次啟動漏加 --website-authorized，於領取／模型呼叫前被拒絕；
  補旗標後消耗原已保存授權，並未建立第二筆 QA 或重跑 Hop。

### 原始執行與隔離重播

規格 `f5fff67d-f2ac-4058-8376-596c9f1bec1f`；日期上下界及空值 filters
通過 deterministic validator，DDL 僅 CREATE 新表。原始 Hop 寫入 ai_sample 專用表一次。
獨立標準答案與實際 Vertica 結果：A=150.2500／2 筆，B=200.0000／1 筆。

- EXACT_MULTISET MATCH：expected 2、actual 2、missing 0、unexpected 0。
- 結果 SHA-256：`54ecba0eab9ec825f3827c080eb90a98ff43a372cdb86043b1c6493a300acdf5`。
- 七個節點、WRITE_STARTED／EXECUTION_RESERVED／HOP_EXECUTED_QA_REQUIRED 各一次。
- 可攜候選 `dd4ce4bb-490e-4186-9aca-64108081f16d` 在隔離 Vertica 25.3.0-2 執行
  原始 HWF/HPL/DDL，PASS；check `22b1ebc7-1b62-4038-b9e2-726e09684207`，結果同為 2/2。
- 正式核准後再次唯讀查詢原目標，仍 MATCH 2/2，無重複寫入。

### 交付與限制

- Release `e844e931-7358-4542-9b6d-0281230a467c`：RELEASE_READY。
- 下載 10,657 bytes，SHA-256
  `ccf5e51a199f0b523a86b0c6a9b55f49e7c2ab44464328cb5e9098be14a63495`。
- 本機：D:\ChatGPT\hop_transfer\outputs\workbench-date-20260926\Release.zip。
- ZIP 只有五個核准產物及 manifest，全部產物 hash 一致；包含 SDM XML 在內，
  未發現已知 runtime host/path、來源檔或常見私鑰/token 標記。非全面秘密偵測保證。
- 瀏覽器交付頁實際顯示正式核准、可攜 PASS、相同 SHA 與下載連結。
- 舊成果區仍顯示 legacy Task 尚未成功；不得與正式 Run 混為一談，列入第 5 階段顯示修正。
- WSL 暫時保持程序到期後容器曾正常停止；恢復後讀回核准與資料不丟失、未重跑。
  Windows/WSL 常駐維運仍屬第 7 階段待完成，不因這次恢復成功而結案。
- 這一案例證明日期範圍補正與同 Run 交付；不代表所有 CSV 日期／錯誤路徑均已驗收，
  更不代表第 3–7 階段或完整平台完成。既有 TASK-20260917-0007 Release 未重播或修改。
