# 第 7 階段：維運與復原驗收

狀態：進行中，尚未完成。人工基準延後不等於其他工程驗收可略過。

## 2026-09-27：既有 PostgreSQL 備份的實際隔離還原

核對先前私有備份：1,370,878 bytes，SHA-256
`f5aae12cd99a5d77717a325e2d8892afe13472549d1ff016bee656d50bf02672`。
備份本體、私有資料及加密密文不納入 Git。

建立全新 PostgreSQL 17 容器，`--network none`、無 host port、未掛載正式
資料卷。沒有 API、Worker 或模型連線。使用 `pg_restore --exit-on-error
--single-transaction --no-owner --no-privileges` 還原至獨立 `restore_drill`
資料庫，exit 0。這不驗證原始 roles／ACL，不能宣稱權限完整復原。

還原後驗證：

| 項目 | 實測結果 |
|---|---|
| 最新 migration | 053_pilot_attempt_order.sql，符合這份舊備份時點 |
| Task Run | 305 |
| Run event | 2,861 |
| Cohort | 1 |
| Release delivery | 24（全庫歷史交付，不是正式 20 案分母） |
| 加密 secret entry | 1；未讀出或解密 |
| 非內建 triggers | 39 |
| 未驗證 constraints | 0 |
| 無效 indexes | 0 |
| Run snapshot immutable trigger | 實際拒絕變更；例外子交易回滾，PASS |

測試後停止隔離容器，保留其副本與資料卷供複查；未刪除或改動正式資料。
此結果是「指定 DB 備份可以實際還原」，不是 HTTP health check 或僅列出 TOC。

## 尚未證明

- 最新 migration 055 的一致性備份及還原。
- 加密主金鑰與 ciphertext 的配對復原及可用性（不得輸出明文）。
- uploads、Hop 產物、SDM、Release ZIP 的完整備份及 checksum 還原。
- 還原環境只讀啟動後，API／逐案 release gate 與實際下載一致。
- 持久 WSL／native worker lifecycle；不依賴四小時 keepalive。
- 重啟／中斷後狀態不丟失、寫入結果不明時不自動重跑的正式驗證。
- 同版 migration／API／worker image 的啟動與回復流程。
- knowledge-workspace 持久化同步仍未完成。

## 下一步

先建立可重現的隔離整體復原流程：停止還原環境派發能力、保持無外部網路，
納入新備份、密鑰與產物的私有副本，再以只讀 API 核對。不得把正式 volume
直接掛成還原環境的可寫資料，不得以修改既有 migration ledger 來繞過版本檢查。
