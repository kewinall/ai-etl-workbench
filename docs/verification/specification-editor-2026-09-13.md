# 欄位式規格建立／編輯

2026-09-13 已部署 Task → 需求與規格 → ETL 規格版本的「建立規格」及「以此規格編輯新版」。保留歷史，不直接修改既有版本。

新 `GET .../specification/editor-context` 從 Run 及最新命名契約取得來源欄位、聚合輸出、型別、目標及 checksum 綁定。缺少命名、draft、過期輸入或規格前置條件不符時阻擋，不要求操作員手填 UUID／checksum。回應不包含篩選或聚合的自動推測。

表單提供明確的全部資料／篩選選擇、條件欄位與比較值、分組勾選、聚合方式、輸出順序。聚合輸出必須先存在於已確認 NamingContract。目標變更仍需 Run 補正。保存前須勾選確認，伺服器重驗契約；保存不代表核准，也不代表 SA／Developer 審查完成或可執行。

整數超出 JavaScript 安全整數範圍會阻擋，不四捨五入；Decimal 保留字串。Timestamp 值比較仍不支援，空值條件可用。此限制不改變完整平台目標，後續需補全型別操作能力。

## 驗證

- 本機 editor／規格回歸 42 passed。
- 容器內 9 passed，含 7 項真實 PostgreSQL 規格 API 及 2 項純 context 測試。新 API 確認綁定保存的 Run／Naming checksum、無連線設定洩漏、上游需求異動後 BLOCKED。
- TypeScript／Vite 與 API／web image 建置成功，服務已部署，CONTROL Worker 恢復，沒有追加模型請求。
- 全站瀏覽器 9 passed（23.1 秒），2 opt-in skipped。規格測試使用合成 API 回應，驗證讀取欄位、修改 Decimal 條件、精確 POST 內容、勾選前禁止保存、保存提示、新建沒有預選篩選模式及取消。

## 未完成與下一步

- 真實 UI→保存→核准→DB→時間線連續驗收仍未完成，分層測試不能替代它。
- 命名契約缺少聚合欄位時需先補正，這個表單不會自動建立命名；完整 Naming UX 仍需端到端檢查。
- 欄位型別操作完整性、草稿離頁保護、錯誤表單逐欄提示仍可改善。
- Worker／來源不可變 bytes／Vertica QA／HWF／DDL／SDM／Release、四案例與 P3 成效均待完成。P0–P3 尚未達標。
