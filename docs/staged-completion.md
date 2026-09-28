# 七階段完成與上版追蹤

## 目前判定（2026-09-28，依已保存驗收證據）

本段是目前索引；下方帶時間的工程補充保留當時狀態，不代表最新結果。
未重新執行已交付 ETL，也不以文件更新取代執行驗收。

| 順序 | 已有證據 | 尚未完成／邊界 |
|---|---|---|
| 1 | 乾淨副本部署基準及階段 GitHub 提交 | 不代表舊 Windows DB 已遷移；見 [部署驗證](verification/clean-deployment-2026-09-26.md) |
| 2 | 日期補正、新 revision、真實執行與 Release | 指定案例通過；見 [日期驗收](verification/date-range-stage2-2026-09-26.md) |
| 3 | Join 語意攔截、真實 QA、可攜重播及節點驗證 | 指定案例通過，不擴大為所有 ETL 功能均已支援 |
| 4 | 真實缺欄位失敗、診斷、核准修訂及新版交付 | 歷史與節點回歸範圍見 [網站驗證](verification/stage5-current-status.md)，不以通用 UI 測試代替每案證據 |
| 5 | 15 項隔離 UI 回歸及三項正式唯讀回歸通過；來源選項輔助說明隱藏與過度承諾文案已修正部署 | 全站完整功能對照、Excel／JSON／資料表及範例來源新版受控流程仍未完成，不能以提示限制取代實作；見 [第 5 階段](verification/stage5-current-status.md) |
| 6 | 20／20 可交付、19／20 原凍結情境匹配；報告已部署 | 第 19 案是核准的來源列序需求延伸；人工基準延後、改善率不可用，完整列印分頁仍待驗證；見 [第 6 階段](verification/stage6-current-status.md) |
| 7 | migration 056、準備失聯核對、正常停啟及手動 WSL session；協調備份與 20 份 ZIP HTTP 還原；同一 execute_once Run 真實部分提交、容器死亡、自然 lease 回收、禁止重跑及真實網站人工結案通過 | 完整 dispatcher 派發鏈、容器外孤兒、宿主機重開／登入自啟與長時間穩定性、異機加密保管／保留策略、原 roles／ACL 及 workspace 同步仍未完成；見 [第 7 階段](verification/stage7-current-status.md) |

整體目標保持未完成。人工基準依操作者決定保留未量測，不填入估算或代理工時。

2026-09-28 來源基礎補充：[共用型別建議與三格式真實上傳驗證](verification/source-type-inference-2026-09-28.md)
已部署；未改變 Excel／JSON／資料表完整執行尚未完成的判定。

同日後續：[Excel 工作表與標頭確認](verification/excel-selection-2026-09-28.md)
已完成真實來源建立及回讀，最終 16 項隔離網站與 3 項正式唯讀回歸通過；
Excel Hop／Vertica／Release 與其他原規劃缺口仍未完成。

## 歷史進度（以下數字與判定以各段日期為準）

最新工程補充（2026-09-27 17:42）：正式量測已重驗凍結來源／答案與父版本缺口、語意拒絕或失敗修正證據，真實 19/20 符合；第 19 案仍被 QA 阻擋。詳見 [凍結情境證據](verification/pilot-scenarios-2026-09-27.md)。未宣稱階段 6–7 完成。

最新工程補充（2026-09-27 17:29）：正式量測已加入模型用量覆蓋，包含所有舊版及失敗紀錄；缺漏不補零、credits 不換算無依據的成本。獨立 SQL／API 與真實 UI 驗證通過，詳見 [模型用量覆蓋](verification/pilot-usage-2026-09-27.md)。階段 6–7 仍未完成。

最新工程補充（2026-09-27 17:22）：專案评估頁已接通固定集合唯讀量測，真實 API／瀏覽器逐案核對 19/20 可交付、47 準備版本、27 補正。人工工時、首次通過率、成本及改善率仍未量測；不以交付數取代它們。詳見 [正式案例量測](verification/pilot-measurements-2026-09-27.md)。階段 6–7 仍未完成。

最新補充（2026-09-27 17:14）：第 20 案已完成真實失敗、診斷、新版修正、QA、隔離可攜重播與正式交付。重新查詢全部 20 案，目前 19/20 RELEASE_READY；第 19 案仍有列序歧義，未放行。證據與未完成範圍見 [第 20 案驗收](verification/recovery-null-stage6-2026-09-27.md) 與 [QA 補正入口](verification/qa-correction-2026-09-27.md)。這不是階段 6 或整體完成宣告；下列歷史進度保留。

更新：2026-09-26。追蹤 knowledge-workspace WS-0007。

| 順序 | 交付與驗收 | 狀態 |
|---|---|---|
| 1 | 可重現基準、機密排除、回歸測試與 GitHub 版本 | 基準驗收通過；部署前置條件與限制見下方證據 |
| 2 | 日期範圍補正、新 revision 與真實執行 | 日期案例驗收通過；同 Run 真實模型、Hop、Vertica、QA、可攜與 Release 已驗證 |
| 3 | 多來源 Join、INNER/LEFT 語意攔截與節點證據 | 指定案例真實 QA、隔離重播及正式 Release 通過；零列節點觀測修正通過原生 HPL/HWF 驗證 |
| 4 | 缺欄位失敗、診斷、人工核准修正及新版本成功 | 真實失敗、診斷與修正版 Hop／QA／隔離可攜／Release 已通過；完整歷史／節點／窄版互動驗收仍待完成 |
| 5 | 真實成果頁、專案評估、全站互動與窄版回歸 | 未完成 |
| 6 | 20 案例、人工基準、完整分母及主管報告 | 未完成 |
| 7 | 操作者啟停、Worker、備份還原及維運驗收 | 未完成 |

## 上版規則

第 4 階段前置證據與未完成事項：[失敗診斷與修訂](verification/failure-stage4-2026-09-26.md)。

第 1 階段最新判定：[乾淨副本部署驗證](verification/clean-deployment-2026-09-26.md)。
以下進度段落保留當時的未完成紀錄，不應覆蓋最新判定。第 2 階段證據見
[日期驗收](verification/date-range-stage2-2026-09-26.md) 最新段落；第 4–7 階段仍未完成。

- 每階段有獨立提交；先驗證後標示通過。中間進度可以提交，但必須註明未完成，不製造假驗收標籤。
- 每次 push 後核對遠端 commit；不 force push、不改寫歷史、不上傳 .env、機密、來源資料或資料庫備份。
- 完整案例已有 RELEASE_READY，不重跑、不修改；新的情境使用獨立 Task/revision。
- 模型費用、正式核准與人工工時是實際輸入，缺失時保留阻擋，不以合成值冒充驗收。

## 第 3 階段目前進度

2026-09-26 21:43：已補 `PipelineFinish` 權威節點 counters（含零筆），不以缺失摘要猜零。
HPL/HWF 各驗零 discard、全部空來源與缺檔失敗，共六項原生驗證通過；連同負向 parser
測試 16 passed。完整隔離回歸 1025 passed／46 skipped／1 warning（23.94s）。
舊 BASIC-only 日誌仍可讀；新 metrics 若缺漏、重複或與 BASIC 衝突，一律不判成功。
第 3 階段指定驗收已通過，下一步第 4 階段缺欄位失敗、診斷與核准修訂成功。

2026-09-26 21:30 最新：QA context/prompt v5 綁定原 HPL 選項及明確標記的獨立引擎探針，
同次補證複核 PASS；v4 NEEDS_REVIEW 原樣保留，未重跑原始 Hop。
SDM、隔離 HWF 重播、正式 Release 及下載 ZIP 的五份產物 checksum 驗證通過。
Release `674f0d82-895b-4d4e-97d1-1c97b29a012f`，ZIP SHA256
`d313deaf6f1f3103bc9aecb0e57fa08c3e4e65e2059e18a8a90e6f5404d25a9d`。
新版定向測試 32 passed；隔離 PostgreSQL 1015 passed／40 skipped／1 warning。
下一步先修 zero-row 節點的權威執行證據，再推進第 4 階段；第 4–7 階段仍未完成。
以下為歷史進度，不代表目前交付狀態。

最新真實案例：TASK-20260926-0014，LEFT Join 已一次執行並與事前答案 MATCH 9/9；
真實 QA 要求補明確空字串／不 trim／超長及解析失敗行為證據，仍為 NEEDS_REVIEW。
不要重跑原始 Hop 或改寫 QA 歷史；後續先補有依據的同次執行複核，再進入可攜與 Release。

已另驗證原生 CSV 空字串／空白／非法整數（3 passed），隔離 Vertica 的 32-byte 成功、
33-byte ASCII／UTF-8 失敗且未保存（3 案例符合預期）。尚未接入同次 QA 複核。
另發現 zero-row discard 不出 BASIC 節點摘要而被判 UNKNOWN，須補權威 metrics，不能猜測為零。

最新入口驗證：雙 CSV 正常建立／上傳／來源限定命名已補齊，網站實際 API 互動通過；
完整隔離回歸 1008 passed／37 skipped，網站新建與規格互動 3 passed（4.7s）。
尚未呼叫此案例的真實模型或執行 Join 寫入；完整第 3 階段仍未完成。
最新證據：[Join 驗證紀錄](verification/join-stage3-2026-09-26.md)。

已新增獨立 `JoinContractV1`，不向既有 `RequirementConditionsV1` 加入預設欄位，
避免改變已交付單來源版本的 canonical document。Join 條件可透過既有 Run revision
API 補正並重新核准；SA evidence 僅包含白名單语意欄位。

已接上每來源 CSV 契約、逐檔 preflight、獨立暫存副本與 revision；正式 Hop／交付仍待接通。
V2 已接 Join 語意攔截、來源限定命名／型別驗證與正向 Hop DAG 編譯；
多來源執行現在使用完整 source-set 的 v3 授權；仍須通過全部既有核准與執行檢查。
原生 Hop Join 八組語意案例與發佈檢查另行通過（9 passed、34.64s；四組使用正式 compiler 產物）；
確認須排除右側 null 鍵，不能直接沿用 MergeJoin 的 null 匹配行為。
多來源 staging／prepared integrity／Hop CLI 參數已接通；另有 2 個真實 Hop CLI 案例通過，
但核准載入為測試替身，正式授權及 Vertica 仍待接通。
Developer 現在依來源數選擇 V1／V2 context、proposal schema 與 prompt；V1 歷史格式不變。
雙來源引用 Join／CSV evidence，仍須通過 deterministic specification validator；模型不授予執行權。
API 核准預覽、保存 intent、gateway 與 local bridge 使用一致的版本與 checksum。
雙來源版本校驗已接入 reservation／write guard；QA context v4 同時保存兩來源解析證據與 Join intent。
已通過隔離 PostgreSQL API 保存／核准、實際授權／reservation／write marker 與 oracle 綁定測試；
測試未呼叫 Hop 或 Vertica，尚非真實派送驗收。
雙來源 HWF／參數模板、SDM 來源對照及 Join 規則已接通；原生 HWF 成功／缺右檔兩例通過。
Portability replay 與 proof v2 已接兩份來源，但 replay 的資料庫／引擎整合仍待真實驗收。
最新控制平面回歸：1004 passed、37 skipped、1 warning（22.58s），exit 0。
新增 8 個 opt-in 原生測試在此環境跳過，但已在上述禁止網路的 Hop 環境實際執行。
此進度**不是多來源同 Run 模型／Hop／Vertica／QA／Release 端到端驗收**。
規格／SDM 的 Join 審查 UI 已通過 V1/V2 瀏覽器測試；Pilot API／Worker／web 已重建。
新建 Task 仍缺雙 CSV 選項及建立政策，須補正常入口與命名流程後才能進入真實案例。
詳見 [Join 階段證據與下一步](verification/join-stage3-2026-09-26.md)。

## 第 1 階段進度

遠端基準為 120660d。原隔離測試 Compose 依賴只有本機存在的
ai-etl-hop-adapter-test:local，無法從 checkout 直接重建。已改為從
deploy/Dockerfile.backend 的 runtime target 建置專用 regression image。
此控制平面測試不包含 Hop/JDBC 真實整合，原生測試另行執行。

重現命令（repository 根目錄的 WSL/Linux）：

```sh
docker compose -f deploy/compose.p0-tests.yml build tests
docker compose -f deploy/compose.p0-tests.yml up --abort-on-container-exit --exit-code-from tests
docker compose -f deploy/compose.yml build web
```

目前已在舊測試映像重跑 844 passed、23 skipped、1 warning（20.18s）；
新可重建映像再次驗證為 844 passed、23 skipped、1 warning（20.45s），
網站 Docker build 成功（可重用 cache）。不得把 skip 視為通過。

上版前檢查 532 個 Git 候選檔案：未發現常見 token/private-key 格式；
無 ZIP、JAR、資料庫、工作簿或大型二進位檔。CSV 僅既有合成 examples
與 70-byte compiler fixture。本機 .env 比對未取得可比較機密值（0 個），
因此不宣稱已完成保管庫實際值掃描或全面安全稽核。

已知另有 Worker 對本機 Vertica image/JDBC 的相依；必須整理來源與重建方法，
不能因控制平面測試可重建就宣稱整套部署可攜。

### 跳過測試與漏版檢查

2026-09-20 再次隔離回歸：844 passed、23 skipped、1 warning（20.37s）。
現在預設輸出 `-ra`，讓 skip 原因可查閱：

| 類別 | 數量 | 處理方式 |
|---|---:|---|
| 原生 Hop／Worker 執行環境 | 10 | 在明確 opt-in 的原生容器／WSL runner 執行；不可在普通控制平面測試假造通過 |
| 指定持久化 Run 證據（reconciliation、QA context/dispatch/journal） | 12 | 需要綁定實際案例，採專用驗收；不能任意重跑已交付版本 |
| Git checkout 檔案發佈檢查 | 1 | 在 repository checkout 執行；測試容器未掛載 .git，故跳過 |

發現 InspectVerticaMetadata.java、VerifyMetadataExport.java 被 ignore，
但原生測試引用它們。已只增加兩檔白名單及 REQUIRED 發佈檢查；
仍忽略憑證、未知 CSV 與其他本機工具。此漏版不能以原本 844 項通過掩蓋。

補充驗證：2026-09-20 原生 Hop metadata roundtrip 測試 2 passed（9.72s），
禁止網路且不連接資料庫、不執行 ETL。2026-09-26 在實際 checkout 重跑
test_source_distribution.py：1 passed（0.08s）。這些證據僅涵蓋 metadata
與發佈檔案完整性，不代表第 1 階段或所有原生整合測試已完成。

### 2026-09-26 乾淨 checkout 驗證

- GitHub `main` 已核對 `ce3eca3c6670adf5642f0d18dc1599dc576efdfa`。
- 從 GitHub 新 clone，未複製原工作目錄的 .env 或未追蹤檔案。
- 發佈檔案檢查：1 passed（0.09s）。
- 原生 Hop metadata：2 passed（9.22s）；使用既有 apache/hop:2.12.0 映像，
  禁止網路，不連接資料庫、不執行 ETL。Python runner 沿用本機 venv，並非乾淨 Python 環境。
- 完整控制平面回歸另在 `ai-etl-clean-regression` 隔離 Compose 專案建置與執行；
  實測 844 passed、23 skipped、1 warning（20.64s），程序 exit 0。
  全新測試資料庫、無發布埠、internal network；結束後容器正常停止，volume 保留。
  測試 image ID：sha256:a9c2d0ae9b736ba5ce7214f717ebeef5c02d834354658eac9319b8dc2d465677。
- 新發現：boto3 使用下限版本，間接 Python 相依亦未鎖定。
  即使回歸通過，也需補齊相依鎖定才可宣稱版本可重現。
- Worker 仍由 local/vertica:25.3.0-rpm 取得 JDBC；本機映像存在不代表其他電腦可建置。

### Python 部署相依版本鎖定

`backend/constraints-linux-py312.txt` 記錄上述通過回歸的 Linux CPython 3.12
映像實際套件版本。Docker runtime/API/Worker 共用 `pip install -c ...` 與
`pip check`；一般 Windows 開發環境仍使用 requirements.txt，不強制安裝 Linux 專用套件。

隔離回歸啟用 `WORKBENCH_VERIFY_DEPENDENCY_LOCK=1`，檢查所有鎖定版本及
目前平台適用的相依是否完整，避免只留下沒被安裝流程使用的清單。
更新直接需求時須同步檢視 constraints，重新執行完整隔離回歸後才能上版。
這是套件版本固定，不是下載內容 hash 鎖定、漏洞掃描或 OS/JDK 映像固定；
也不代表真實模型相容性驗收。

2026-09-26 鎖定後重新 Docker build 與 `pip check` 成功，獨立
`ai-etl-locked-regression` 回歸：846 passed、23 skipped、1 warning（20.04s），
exit 0。兩個新檢查均執行通過；容器正常停止、測試 volume 保留。

### Worker JDBC 解耦

已改為外部檔案 build context 加 SHA-256 驗證；Worker 不再依賴本機 Vertica
image 取得 JDBC。詳見 [建置與實測](worker-jdbc-build.md)。正確檔案成功、
錯誤 checksum／缺少目錄／缺少 JAR 皆拒絕；完整 Worker build 成功，
無網路 Hop adapter 2 passed（6.04s），隔離回歸 848 passed／23 skipped／1 warning。
後續仍需以提交後的乾淨 checkout 核對完整部署入口；portability 測試資料庫的
本機 image 前置條件與 OS image 漂移等限制必須保留，不冒稱一鍵部署全部完成。

### 階段 2 日期範圍進度（2026-09-26）

已接通日期 Filter 與已確認期間的一致性檢查，並驗證缺口補正的新 revision
及重新核准。隔離回歸 863 passed／25 skipped／1 warning；禁網原生 Hop
日期邊界 2 passed。詳見 [證據與限制](verification/date-range-stage2-2026-09-26.md)。
尚缺新案例同 Run 真實模型、Vertica 逐筆標準答案與 QA；階段 2 未完成。
