# 七階段完成與上版追蹤

更新：2026-09-26。追蹤 knowledge-workspace WS-0007。

| 順序 | 交付與驗收 | 狀態 |
|---|---|---|
| 1 | 可重現基準、機密排除、回歸測試與 GitHub 版本 | 基準驗收通過；部署前置條件與限制見下方證據 |
| 2 | 日期範圍補正、新 revision 與真實執行 | 日期案例驗收通過；同 Run 真實模型、Hop、Vertica、QA、可攜與 Release 已驗證 |
| 3 | 多來源 Join、INNER/LEFT 語意攔截與節點證據 | 進行中；契約、編譯、Developer V2 交接已驗證，正式執行與交付未完成 |
| 4 | 缺欄位失敗、診斷、人工核准修正及新版本成功 | 未完成 |
| 5 | 真實成果頁、專案評估、全站互動與窄版回歸 | 未完成 |
| 6 | 20 案例、人工基準、完整分母及主管報告 | 未完成 |
| 7 | 操作者啟停、Worker、備份還原及維運驗收 | 未完成 |

## 上版規則

第 1 階段最新判定：[乾淨副本部署驗證](verification/clean-deployment-2026-09-26.md)。
以下進度段落保留當時的未完成紀錄，不應覆蓋最新判定。第 2 階段證據見
[日期驗收](verification/date-range-stage2-2026-09-26.md) 最新段落；第 3–7 階段仍未完成。

- 每階段有獨立提交；先驗證後標示通過。中間進度可以提交，但必須註明未完成，不製造假驗收標籤。
- 每次 push 後核對遠端 commit；不 force push、不改寫歷史、不上傳 .env、機密、來源資料或資料庫備份。
- 完整案例已有 RELEASE_READY，不重跑、不修改；新的情境使用獨立 Task/revision。
- 模型費用、正式核准與人工工時是實際輸入，缺失時保留阻擋，不以合成值冒充驗收。

## 第 3 階段目前進度

已新增獨立 `JoinContractV1`，不向既有 `RequirementConditionsV1` 加入預設欄位，
避免改變已交付單來源版本的 canonical document。Join 條件可透過既有 Run revision
API 補正並重新核准；SA evidence 僅包含白名單语意欄位。

已接上每來源 CSV 契約、逐檔 preflight、獨立暫存副本與 revision；正式 Hop／交付仍待接通。
V2 已接 Join 語意攔截、來源限定命名／型別驗證與正向 Hop DAG 編譯；
多來源執行仍由 runtime authorization 明確阻擋。
原生 Hop Join 八組語意案例與發佈檢查另行通過（9 passed、34.64s；四組使用正式 compiler 產物）；
確認須排除右側 null 鍵，不能直接沿用 MergeJoin 的 null 匹配行為。
多來源 staging／prepared integrity／Hop CLI 參數已接通；另有 2 個真實 Hop CLI 案例通過，
但核准載入為測試替身，正式授權及 Vertica 仍待接通。
Developer 現在依來源數選擇 V1／V2 context、proposal schema 與 prompt；V1 歷史格式不變。
雙來源引用 Join／CSV evidence，仍須通過 deterministic specification validator；模型不授予執行權。
API 核准預覽、保存 intent、gateway 與 local bridge 使用一致的版本與 checksum。
雙來源版本校驗已接入 reservation／write guard；QA context v4 同時保存兩來源解析證據與 Join intent。
這些程式路徑已接通並有定向測試，但正式多來源授權仍阻擋，尚非真實派送驗收。
雙來源 HWF／參數模板、SDM 來源對照及 Join 規則已接通；原生 HWF 成功／缺右檔兩例通過。
Portability replay 與 proof v2 已接兩份來源，但 replay 的資料庫／引擎整合仍待真實驗收。
最新控制平面回歸：1002 passed、37 skipped、1 warning（22.17s），exit 0。
新增 8 個 opt-in 原生測試在此環境跳過，但已在上述禁止網路的 Hop 環境實際執行。
此進度**不是多來源執行或 INNER/LEFT 語意攔截驗收**；仍保留 runtime blocker。
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
