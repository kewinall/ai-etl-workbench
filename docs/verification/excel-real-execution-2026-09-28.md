# Excel 真實模型與 Hop／Vertica 驗收進度（2026-09-28）

## 結論

新建獨立合成案例完成真實 SA、Developer 與單次 Hop／Vertica 寫入；
唯讀查核的實際結果與固定答案一致。但原本的執行後答案讀取器拒絕 V4 授權，
導致正常派發結果停於 `NEEDS_REVIEW`，**尚未完成 QA 或 Release，不算 E2E 通過**。
既有 20 案集合及歷史交付未重跑。

## 案例與保留歷史

- Excel 工作表「明細」，第 2 列標頭；6 列中 1 列全空白，按 SKIP 政策保留 5 筆。
- 中文欄位對應 category／amount；amount > 100.00、排除 NULL 比較，再依 category 聚合。
- 固定答案在 Hop 前保存並核准：A 合計 150.25／1 筆，B 合計 500.50／2 筆；忽略結果列序。
- 初次準備時，來源宣告保留 4 位小數，但人工命名輸入只有 2 位；
  後續型別檢查發現此精度縮減，沒有放寬編譯器。保留首版 SA 與用量，經正常 revision API
  建立補正版，amount 改為 NUMERIC(18,4)、total_amount 為 NUMERIC(24,4)，重新核准／審查。
- 首版與補正版 SA 均使用 prompt v7；補正版 Developer v7 產出 V4 規格，
  人工／程式核對原生 Excel 引用、篩選、聚合、輸出與三重來源指紋後核准。
- 共 3 次真實 Copilot gpt-5.4 呼叫：兩次不同 revision 的 SA、一次 Developer，
  各 1 session、0 automatic retries、0 tool executions。回報為 PARTIAL usage，
  AI credits 分別 5.64275、5.20525、4.81615；缺少完整 Token，不能自行補估費用或工時。

## 實際缺陷與修正

1. 真實 Hop 結果為 COMPLETED、exit 0、errors 0，有私有 log checksum 及唯一 WRITE_STARTED。
2. 外層派發停為 `HOP_PREPARATION_OR_COMPARISON_FAILED`，Run 仍保留 `HOP_EXECUTED_QA_REQUIRED`；
   查核沒有已保存 comparison。沒有重新執行、不 DROP、不修改已執行規格或歷史。
3. 對正式 API 進行唯讀診斷，精確重現 `execution_oracle.py` 的
   `EXECUTION_ORACLE_BINDING_CHANGED`；授權 policy allowlist 只接受 v2／v3，漏接 Excel v4。
4. 修正為接受 v4，但強制再次核對 XLSX 格式、來源內容指紋、已確認來源契約與單來源限制；
   拒絕缺格式、假 CSV、降級 v2、來源 hash 改變、多來源形式及未知版本。
5. 既有私有答案、核准、execution reservation、log、query checksum 保護仍維持。
   新增真實隔離 PostgreSQL 的 execution→oracle→pinned query 回歸；該測試使用明示替身 engine。

## 已驗證結果

| 項目 | 證據 |
|---|---|
| 新增格式／防降級檢查 | 8 passed |
| 全後端隔離回歸 | 1689 passed、105 skipped、1 warning，37.19 秒，exit 0 |
| 真實 Vertica 唯讀比對 | MATCH；expected=2、actual=2、missing=0、unexpected=0 |
| 不重跑保護 | 查核前後事件筆數完全一致；WRITE_STARTED 仍只有 1 次 |
| 查核範圍 | 使用原本核准的 compiler-pinned SELECT、原設定指紋、目標擁有權及空表／寫入前證據；不是任意 SQL |

唯讀查核透過獨立單次容器，唯讀掛入已通過回歸的 loader 修正；沒有保存 PASS、comparison、
QA 或 release，也沒有直接修改控制資料庫來把失敗派發改為成功。正式 API 尚未部署這個修正。
原 Hop 與診斷容器均已終止且保留；來源檔、原始 trace、執行識別碼與私有進度只留本機，不進 Git。

## 具體下一步

1. 實作並驗證顯式「重做結果比對、禁止重跑 ETL」流程。僅接受 Hop 已確定完成、
   原派發因後處理失敗而停止、版本及目標 provenance 仍有效的 Run。
2. 保存新的 comparison／provenance 及後處理恢復事件，保留原 NEEDS_REVIEW 歷史；
   綁定人工確認、防重複請求、確認沒有活躍 Worker，不授權第二次資料寫入。
   不得用直接 SQL 改派發狀態或重新跑原 Hop 取代此流程。
3. 在同一補正版接續真實 QA、SDM 與獨立目的環境的 HWF 可攜重播，最後核准 Release ZIP。
4. 本案未列入原凍結 20 案集合，不改變原分母或刪除不通過紀錄；第 5–7 階段仍未完成。

人工基準仍依操作者決定未量測。knowledge-workspace 既有寫入限制未繞過，
本次尚未持久化至 knowledge-workspace；具權限接續時同步 WS-0007 的本證據與下一步，
不公開私有執行識別碼、原始資料、憑證或主機資訊。
