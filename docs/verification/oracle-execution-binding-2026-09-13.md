# 標準答案與單次執行授權綁定

## 根因與修正

原 `hop-single-attempt-v1` 授權只包含來源、規格與設定，未包含答案。因此原本授權指紋不能表達答案改版。本輪升為 v2，於既有 JSON binding 增加 oracle_id、oracle_version、oracle_checksum、oracle_approval_id，無另建 Task 系統或 migration。

offer 在 Task lock 內取得最新答案與核准，解密核對 Run／規格／命名指紋，並重新驗證目前答案型別限制。缺少答案或核准即拒絕。authorize、reserve 與 begin_external_write 沿用相同 offer 再驗證，因此原 v1 授權或答案改版後的舊授權無法通過指紋比對。沒有默認答案、空白替代或自動核准。

答案綁定是執行前提，不是 QA 通過。執行後仍須以授權內指定的不可變答案與真正 Vertica 結果比對，不能任意選新的最新答案。

## 驗收

- 隔離 PostgreSQL 授權／原子領取／合成 Worker／答案保存：9 passed、1 skipped，3.87 秒。跳過 native Hop adapter opt-in 測試；測試 executor 為合成，不是實際 Vertica 寫入。
- 缺少答案、未人工核准、答案改版後 authorize／reserve 舊授權被拒絕，write_started 維持 false。
- 既有單次領取、租約到期、COMPLETED／FAILED／UNKNOWN 保存與加密 log 綁定仍通過。
- 安全後端回歸 382 passed、73 skipped，5.20 秒；排除舊主機 DB test_api.py。
- API／CONTROL 已重建部署。網站規格及答案保存／核准／歷史回讀 1 passed，6.2 秒；Task TASK-20260913-0195。

## 邊界

此授權／單次执行仍是內部受控流程，正式執行 API／UI 尚未接通。未開啟 WORKBENCH_EXECUTION_ENABLED 或模型派發，沒有新增模型呼叫或 Vertica 寫入。真實目標 metadata、Vertica 結果讀取與持久 QA、SDM、Release、四情境及 20 案例未完成。既有歷史授權不覆寫，v1 不再可用；不可無人工重新確認直接升級成 v2。
