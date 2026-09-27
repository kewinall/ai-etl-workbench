# 第 7 階段：維運與復原驗收

狀態：進行中，尚未完成。人工基準延後不等於其他工程驗收可略過。

## 準備失聯核對網站表單（隔離網站驗證）

Hop 單次執行區的 CLAIMED／NEEDS_REVIEW 請求可讀取準備失聯核對狀態，
沿用既有核對元件增加明確模式，不移除原執行結果核對。新表單區分目標
不存在（null）與存在零筆（0），必須確認停止程序、查核目標、同意只結案，
本機證據檔只計算 SHA-256 不上傳；保存後重載整個 Run，避免沿用舊按鈕狀態。

前端 build 通過，500 kB chunk 警告仍存在。新 API／web 只部署隔離 5195，
其 DB 套用 056；正式 API／DB／web 未更新。瀏覽器使用正式既有版本的 GET
資料作導覽參考，結案 GET／POST 全部 synthetic routes，禁止轉送其他寫入。
兩種目標情境、必填、正確 payload、重載與 390px 寬度 **2 passed（4.9 秒）**。
中途重跑曾因測試結束時 request context 先被釋放而 2 failed；加上等待
route callbacks 完成後重驗通過，沒有忽略錯誤或減少斷言。

這是表單互動驗證，非真實失聯 DB 的網站結案 E2E；後者、共享舊表單回歸與
正式部署仍待完成。隔離服務測試後停止，合成資料及正式歷史不刪除。

## 準備階段失聯人工結案：後端實作，未部署

新增 migration 056 的 immutable `hop_preparation_reconciliation`，綁原
request／claim 指紋、Run 版本、Operator、證據 SHA-256、目標存在與查核筆數。
新增 GET／POST `hop-preparation-reconciliation`（位於 Task Run 路徑）。
僅接受 CLAIMED、Run NEEDS_REVIEW、未開始寫入且無 lease；明確确认程序停止、
目標已查核及同意才可結案。目標不存在時筆數必須 null，不能以 0 冒充查無表。

結案只將原 dispatch 變 NEEDS_REVIEW、Run 變 FAILED，保留所有 binding／
authorization，不建立新工作、不刪表、不宣稱 SQL rollback 或 QA 通過。
資料是 OPERATOR_ATTESTATION，不冒充平台自動偵測程序死亡或獨立 SQL。
Task／Run／request 交易鎖及 checksum 防止競爭；原 worker finish 被拒絕。
同值重送冪等，不同證據衝突，結案紀錄禁止 update／delete。

隔離 PostgreSQL 定向測試 **3 passed、1 warning（2.66 秒）**：原流程、
不存在目標、存在且有筆數目標。首次完整測試因 pytest 參數含預設值與
parametrize 衝突，在 collection 中止；修正測試與呼叫者後重跑，不算通過。
尚未提供網站操作表單，正式 DB 未套 056、正式 API 未部署此功能；真實失聯
副本的人工結案 E2E 及 Vertica 中斷仍待驗證。
修正後完整隔離回歸 **1,477 passed、50 skipped、1 warning（30.84 秒）**，
exit 0；增加的 skip 是需明確啟用的原生 Hop 中斷及專用 DB 程序死亡測試。

## 領取後／執行前的真實程序死亡

新增 opt-in `test_hop_claim_process_loss.py`，只在新的專用隔離 Compose DB
啟用 `WORKBENCH_HOP_CLAIM_DEATH_TEST=dedicated-disposable-database`，不得對
正式或一般回歸 DB 執行。合成角色及核准資料由子程序建立，Hop claim 真正
commit 後通知父程序；父程序實際 kill 並 wait 回收。沒有啟動 Hop 或 Vertica。

死亡後以另一程序的 connection 查核：僅一筆 CLAIMED、write_started=false、
lease_token=null、target claim 0。reap_expired=0，兩次再 claim 皆 None，事件
數不變。**1 passed（2.74 秒）**，專用 DB 停止並保留合成證據，不反覆重用。

重要限制：這證明準備階段 owner 死亡不會重領，**不證明已復原**。請求仍卡在
CLAIMED，現有 Run lease reaper 不處理它；需要明確的失聯查核／人工結案流程，
綁定原 request 與可能 DDL 副作用，不能單憑逾時直接重設 QUEUED。
真實建表後或資料提交中死亡及獨立 SQL 核對仍未驗證。

## 中斷驗收的兩個領取階段

程式查核：`hop_dispatch.claim` 先將請求標為 CLAIMED，之後
`prepare_new_target` 才建立新表，`execute_once` 再取得 Run lease 並標记 write
started。因此 Run lease 逾時測試不能證明準備階段程序死亡的復原行為。
目前不得自動把舊 CLAIMED 重設 QUEUED；準備階段可能已有 DDL 副作用。

新增隔離 PostgreSQL 重複 HTTP 請求驗證：request 已 CLAIMED 時再 POST 原
binding，仍回原 request ID／CLAIMED／automatic_retry=false，全庫同 Run
request 僅一筆、再次 claim 為 None、write_started 仍 false。定向 **1 passed、
1 warning（2.26 秒）**。角色為合成、交易最後回滾，不是程序死亡或 Vertica E2E。

完整中斷驗收仍須分兩條：
1. claim 後／Run lease 前強制死亡：確認 DDL 是否已發生、保留原 request，
   不能靠時間猜無副作用或自動重新建立表。
2. lease 後／資料提交中死亡：使用新受控目標、獨立連線確認已提交 rows、
   失聯後 NEEDS_REVIEW／UNKNOWN，重啟不能重新寫入；保存人工核對證據。
這是仍待執行的驗收契約，並非通過結果；不可使用現有已交付目標演練。

## 2026-09-28：真實 Hop 處理中取消

新增 opt-in `test_hop_interruption_native.py`。每次使用新 network-none Worker
容器、合成 CSV、既有 compiler HPL 與 Dummy sink；Java probe 在 target 真正
讀到第一列後寫容器內 marker，等待中的 Python 才觸發取消。不是僅 sleep 的
假引擎，也沒有修改正式 Task、連線 Vertica 或重跑交付。

實際 `run_managed` 終止 Hop 程序並回收，reason=CANCELLED、exit<0，沒有
collector 成功結尾；`hop_log_evidence` 判 UNKNOWN、qa_passed=false。
同時重跑原有 header／無 header 的正常列序案例，**3 passed（13.88 秒）**。
Java 探針僅接受明確 `--interrupt-probe`，既有不帶參數流程保持正常。

這是實際引擎 in-flight 取消及保守結果判定證據；不是 owner 強制死亡、
Vertica 已提交部分資料、佇列失聯後不重跑與獨立 SQL 核對的完整 E2E。
後者仍是未完成驗收，不以本項替代。

## 2026-09-28：migration-aware readiness 已部署

部署前查核正式控制 DB：active leases 0、pending Hop 0、Run events 2,861。
建置 commit `e145a04` API，保留四項既有 true 派發開關，只重建 API，未重建
DB、網站或 Worker，沒有 migration 或 Task 重跑。Compose 的 portability
orphan 提示未以 remove-orphans 處理，既有隔離容器保留。

實際映像 `sha256:fa4c043cd1299d804e1f996bf9d9721c26df90a503928887a67ff5404706d04a`，
Docker health healthy，`/api/ready` 200、execution_enabled=true；此端點已核對
完整 migration 檔案與 ledger。部署後 active leases／pending Hop 仍為 0，
Run events 仍為 2,861。正式量測與成果報告唯讀 Playwright **2 passed（16.8 秒）**，
逐案證據與歷史一致，未觸發寫入或模型。
此段取代下方「尚未部署正式服務」的歷史狀態；完整第 7 階段仍未完成。

## 2026-09-28：正式 bootstrap 與 migration readiness

檢視發現 `/api/ready` 只檢查 DB 可連線與 Task／Project 表存在，缺少完整
migration ledger 核對。新增唯讀 `verify_current`：缺檔、缺 migration、額外
版本或 checksum 不符均阻擋 readiness，不補寫 ledger 或自動修復；僅接受
既有 migration 規則允許的 LF／CRLF／BOM 等價差異。定向 6 項測試通過。

在上一輪全新封裝還原 DB／檔案卷上，用實際 image 預設 `app.bootstrap`
entrypoint 及 password/key file 啟動 Uvicorn。新 backend 與 migrations 以
readonly bind 掛載，root／產物 readonly，所有派發 false，無 Worker、
無 host port、沿用 DB 的 network-none namespace，API 僅綁 loopback。
`/api/ready` HTTP 200 且 execution_enabled=false；20 份 HTTP download 再驗
通過、19 個原凍結情境匹配。驗證後停止隔離 API 與 DB，資料保留。

這次驗證包含 bootstrap 密鑰載入、schema 版本核對與 API 啟動；trust-mode
隔離 DB 不證明密碼認證或原 roles／ACL。沒有 init 重產金鑰或 migration 寫入。
本次 readiness 修改尚未部署正式服務，不將 readonly bind 測試稱為正式上線。
完整隔離 PostgreSQL 回歸 **1,475 passed、48 skipped、1 warning（30.15 秒）**，
exit 0；skip 仍為 opt-in 原生／真實證據等檢查，沒有視為通過。下一步在確認
無活躍工作後建置及部署 API，再以正式 readiness 與唯讀量測回歸確認。

## 2026-09-28：完全從私有封裝還原的新環境

新建無外部網路、無 host port PostgreSQL 17 容器及四個全新檔案卷；
來源只有上一節封裝中的 DB dump 與四份 tar，沒有掛原復原卷或正式卷。
`pg_restore --exit-on-error --single-transaction --no-owner --no-privileges`
還原新 `restore_portable` DB 成功。新解包工具先核對五份 checksum 及 tar
安全路徑、禁止覆寫。第一次因新卷根目錄屬 root、API UID 10001 無寫入權而
失敗；確認四卷仍全空後只調整新卷根目錄擁有者，第二次解包 PASS。
初次失敗不計通過，且 DB 已成功還原，沒有重跑 DB restore 或既有 ETL。

以新 DB＋新卷 readonly 執行 `app.recovery_verify --http`：**PASS**，secret 1、
20 份 service／HTTP 下載通過、19 個原凍結情境匹配、Run／effort events 不變，
ETL replay false，exit 0。完成後停止新還原容器，保留副本；正式服務未停止。
這是同機從封裝的新環境還原證據，不是 offsite、原 roles／ACL、部署 entrypoint
與完整 readiness、live 備份自動協調或真實 ETL 寫入中斷驗證。

## 2026-09-28：從已驗證副本產生私有可攜封裝

新增 `app.recovery_export`，明確 opt-in、來源 readonly、目的地新建 UUID
目錄且不可覆寫。使用前次 migration 055 配對 DB dump（SHA-256 見下方）
與四組既有復原 volumes，network-none helper 匯出至 Windows 本機私有備份
目錄；未使用正式卷、未停止正式服務，也沒有新建 live snapshot。

實測 PASS：一份 DB dump、四份 tar、最後產生 manifest；各 tar 重新讀取，
全部相對名稱、檔案內容雜湊與空目錄皆與來源 inventory 相符。備份本體含
密鑰，僅在本機私有目錄，不納入 Git。合成封裝／禁止覆寫／錯誤 DB checksum
測試 1 passed（1.08 秒），不把合成檔案視為 PostgreSQL 還原證據。

下一步必須從這份封裝（不直接掛原復原卷）還原到新 DB 與新檔案卷，再跑
service-layer／HTTP 驗證。尚未完成此步，不宣稱可攜封裝已可完整復原。
也未驗證 offsite、備份加密、目的地 ACL、roles／ACL 或 live 備份協調流程。

## 復原工具加入後的完整回歸

以 commit `8266acc` 的 checkout 執行既有隔離 PostgreSQL Compose suite：
**1,464 passed、48 skipped、1 warning，35.69 秒，exit 0**。
資料庫與測試容器隨程序完成停止，保留隔離資料卷；不使用正式 DB。
警告為 Starlette TestClient 的 AnyIO BlockingPortal 棄用訊息，未抑制。
資料庫 log 的 immutable／duplicate 拒絕是負向測試的預期行為，suite 判定通過。

48 skipped 不能計為通過，包含原生 Hop、既有真實 QA／執行證據及 Git checkout
可見性檢查。另在 Windows checkout 顯式啟用 network-none 原生 Hop 驗證：
`test_source_order_native.py` 與 `test_hop_final_metrics_native.py`，
**8 passed，36.19 秒**。涵蓋有／無 header、跨行 CSV、重複值來源序號，
以及 HPL／HWF 的零 discard、空來源、缺來源失敗之最終節點 counters。
所有輸出使用 Dummy sink，不連線 Vertica，不能代替真實寫入中斷驗收。
未重跑正式 Task、未呼叫模型，也不將這 8 項之外的 opt-in 跳過案例算入通過。

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
