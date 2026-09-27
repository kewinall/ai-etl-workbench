# 第 7 階段：維運與復原驗收

狀態：進行中，尚未完成。人工基準延後不等於其他工程驗收可略過。

## 全部既有副本檔案比對

新增 `app.recovery_files`，在 network-none、root readonly 的 helper 中逐組
掛載正式檔案卷與既有復原卷，兩側 readonly；沒有改寫或停止正式服務。
比對全部相對名稱、檔案 bytes／SHA-256 及空目錄，未輸出私有名稱或內容。

| 卷 | 檔案 | 子目錄 | bytes | 缺少／多出／變更 |
|---|---:|---:|---:|---|
| secrets | 2 | 0 | 87 | 0／0／0 |
| uploads | 168 | 168 | 14,612 | 0／0／0 |
| artifacts | 0 | 0 | 0 | 0／0／0 |
| outputs | 102 | 97 | 728,080 | 0／0／0 |

四組 PASS。空 artifacts 卷如實記零，不據此推論其他位置沒有歷史產物。
僅證明本次 272 檔案與 265 子目錄掃描相符；不是原子備份、資料庫與檔案
跨時間一致性、ACL／owner／mode、異機備份或復原啟動的驗證。來源未停寫，
不可將此掃描稱為備份時點 manifest。
Windows 測試首次因 pytest 暫存目錄存取權限在 setup 失敗，未視為通過；
改用無網路 Linux 容器暫存空間後通過，包括實際 symlink 拒絕案例。

## 最新：隔離復原 API 真實 HTTP 下載驗證

後續已整合為 `python -m app.recovery_verify ... --http`，不再需要臨時啟動腳本。
同一復原副本以該 CLI 再驗 PASS：secret 1、download 20、frozen match 19、
Run 與 effort 事件不變、HTTP true、ETL replay false，exit 0。短生命週期
server 使用有界啟停，只允許兩類唯讀路徑；復原 DB 另行停止保留副本。
相關定向測試 21 passed（3.03 秒）。初次兩項關閉測試因 Windows 對已關閉
埠回 ConnectTimeout 而非 ConnectError 失敗；增加重新 bind 原埠的直接證據，
並接受這兩種不可連線結果後通過，不放寬 server thread 必須終止的要求。

在既有 network-none、migration 055 復原 DB 上啟動實際 `app.main`，使用
Uvicorn 的 loopback TCP listener，不是 TestClient 或 mock API。沒有 host port、
Worker、外部路由；所有派發旗標 false，副本 volumes 與 root filesystem 唯讀。
額外 middleware 拒絕非 GET；只呼叫量測與已交付版本下載，不呼叫核准或重跑。
API image 為 `sha256:7e275291ae80ff321932f6ff3287920cbeb9ce672fabdbbaa972ce2e604858fc`，
另以唯讀 bind 使用本次 checkout 的 backend；不宣稱這些新增工具已建入正式 image。

新增 `app.recovery_http.verify_http`：拒絕非 loopback URL、環境代理及轉址，
驗證固定 20 案、交付數、每份 ZIP 的 checksum、六個成員、CRC、content-type、
attachment filename、no-store 與 nosniff。合成 transport 正反向測試 **11 passed**；
它們不代替以下真實驗證。

真實 TCP HTTP 結果：**PASS，20 份下載、19 個原凍結情境匹配**。Run event
與 effort event 數量前後不變；未重播 ETL。API 正常關閉、隔離 DB 容器已停止，
副本保留。正式服務未重建或停止。此驗證未涵蓋瀏覽器、完整 readiness／啟動
腳本、roles／ACL、全部歷史檔案、異機復原或真實寫入中斷。

## 真實程序終止後的佇列恢復測試

新增 `test_run_queue_process_loss.py`：隔離 PostgreSQL 合成 Task 經 enqueue／
review 後由獨立 Python 子程序 claim，確認 claim 已提交後真正終止該程序，
再由另一個新程序 reap／claim。測試將合成 lease 調成逾時以免等待真實時鐘；
write_started 由測試種入，**不是實際 Hop／Vertica 寫入中斷**。

兩種情境皆通過：未寫入為 LEASE_EXPIRED，可能寫入為 HOP_RESULT_UNKNOWN；
皆 NEEDS_REVIEW、lease 清除、無法重新 claim、reap 只記一次事件，舊 owner
不可 finish，新 request 不可繞過待核對狀態，相同 request 回原 run。

定向測試 **2 passed（3.73 秒）**；完整隔離回歸 **1,447 passed、48 skipped、
1 warning（35.93 秒）**，exit 0。隔離測試 DB 隨 Compose 停止，正式資料未動。
仍需實際 ETL engine／資料庫副作用存在時的中斷與獨立資料核對驗證，不能以
這項控制平面測試代替。持久啟動模式已詢問操作者，尚未新增 Windows 排程。

## 可重複復原檢查工具

新增 `app.recovery_verify` 及 [執行契約](../recovery-verification.md)，将先前
臨時驗證整理為 opt-in 工具。拒絕非隔離用途的連線、含密碼／query 的 DSN，
檢查 IPv4／IPv6 路由及 readonly mounts；不列印明文或原始 exception。
8 項 scope 單元測試通過。最終版在既有無網路復原副本實測 PASS：
1 筆 secret 解密、20 份 download service／ZIP 指紋完整、19 個凍結情境匹配、
events unchanged。HTTP verified 明確為 false，ETL replayed 為 false。
驗證後停止隔離容器，資料保留。這不是自動備份／還原或完整環境復原工具。

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

## 舊備份演練後的待辦（歷史快照）

以下是 migration 053 演練當時的缺口；前三項已有下節 055 副本的部分證據。
目前剩餘範圍以 055 節末與「下一步」為準，不重複宣稱全部尚未執行。

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

## 基礎容器重啟策略與網站退出驗證

Compose 的 postgres、api、web 新增 `restart: unless-stopped`，control-worker
維持原策略。init／migrate 保留 `restart: no`；沒有開啟原本未启用的執行
profiles。透過 `--profile pilot-control config --format json` 驗證實際解析值。
最初未指定 profile 的檢查沒有包含 control-worker，該次檢查失敗；指定正確
profile 後六個服務的策略檢查通過，不把缺失服務視為已通過。

以 `docker update --restart unless-stopped` 套用三個既有基礎容器，無重建、
無 migration 或工作重跑。對網站執行 `nginx -s quit` 後，同一容器自行恢復：
RestartCount 從 0 變 1、state running，網站 `/api/ready` 回 ready。
過程未手動 start 網站以替代自動重啟。資料庫／Worker 未在這次測試中中斷。
退出恢復後正式量測與報告唯讀瀏覽器回歸：**2 passed（20.6 秒）**，逐案
證據及歷史事件一致。這是網站恢復的驗證，不擴大到未執行的中斷情境。

此證據只涵蓋網站程序退出；不代表 PostgreSQL crash、API in-flight request、
Worker 正在寫入、Docker daemon 或 WSL／Windows reboot 已驗證。手動停止的
服務依 unless-stopped 語意保持停止；沒有修改全域 WSL、Windows 開機排程或
防護軟體。四小時 WSL keepalive 的持久性問題仍待解決。
