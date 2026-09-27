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

## 後續：migration 055 與私有產物副本復原

短暫停止正式 API 與 control-worker，建立新 PostgreSQL custom-format 備份，
並從唯讀正式 volumes 複製 secrets、uploads、artifacts、outputs 至新的私有
復原 volumes。完成後恢復原服務；未刪除或覆寫正式 volume。備份檔 SHA-256：
`ac038d5032754b7630fa081694286e69c3b22df8283f579fda017fb5a3805224`。
副本含機密，僅留在本機 Docker 私有 volume／私有備份目錄，未提交 Git。

同一無網路還原容器中新建 `restore_full_055`，不覆寫前一演練 DB。
單一交易還原成功：最新 migration 055、Run events 2,861、effort events 0。
仍使用 no-owner/no-privileges，不宣稱原 roles／ACL 復原。

驗證工具容器只共用該 `--network none` DB 的 network namespace，以 loopback
連線；全部檔案副本唯讀、容器 root filesystem 唯讀，沒有 API／Worker 派發。
未掛載任何正式 volume。實測結果：

- 副本金鑰成功解密 1 筆既有 secret；只驗證非空，不輸出或保存明文。
- 既有量測服務回讀：20／20 RELEASE_READY、19／20 原凍結情境匹配、
  unverified 0。保留第 19 案需求延伸邊界。
- 驗證前後 Run event 數不變。
- 逐案呼叫實際 Release download service：20 份 checksum 一致，均為 6 個
  ZIP 成員且 CRC 檢查通過，共 204,442 bytes。這是 service-layer 驗證，
  不是 HTTP／瀏覽器下載驗證，也沒有重新執行 ETL。
- 隔離容器已停止並保留副本。正式 `/api/ready` 回 ready、execution enabled。

這證明最新 DB＋複製金鑰＋指定交付依賴可以在隔離副本讀取與通過 gate。
尚未證明所有歷史 uploads/產物逐檔完整、異機／離線備份可用、原 roles／ACL、
HTTP 還原部署、持久 lifecycle 或中斷寫入不重複。上節尚未證明項目應依本次
具體證據縮小範圍，不視為整體第 7 階段完成。

## 下一步

先建立可重現的隔離整體復原流程：停止還原環境派發能力、保持無外部網路，
納入新備份、密鑰與產物的私有副本，再以只讀 API 核對。不得把正式 volume
直接掛成還原環境的可寫資料，不得以修改既有 migration ledger 來繞過版本檢查。
