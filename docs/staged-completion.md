# 七階段完成與上版追蹤

更新：2026-09-20。追蹤 knowledge-workspace WS-0007。

| 順序 | 交付與驗收 | 狀態 |
|---|---|---|
| 1 | 可重現基準、機密排除、回歸測試與 GitHub 版本 | 進行中 |
| 2 | 日期範圍補正、新 revision 與真實執行 | 未完成 |
| 3 | 多來源 Join、INNER/LEFT 語意攔截與節點證據 | 未完成 |
| 4 | 缺欄位失敗、診斷、人工核准修正及新版本成功 | 未完成 |
| 5 | 真實成果頁、專案評估、全站互動與窄版回歸 | 未完成 |
| 6 | 20 案例、人工基準、完整分母及主管報告 | 未完成 |
| 7 | 操作者啟停、Worker、備份還原及維運驗收 | 未完成 |

## 上版規則

- 每階段有獨立提交；先驗證後標示通過。中間進度可以提交，但必須註明未完成，不製造假驗收標籤。
- 每次 push 後核對遠端 commit；不 force push、不改寫歷史、不上傳 .env、機密、來源資料或資料庫備份。
- 完整案例已有 RELEASE_READY，不重跑、不修改；新的情境使用獨立 Task/revision。
- 模型費用、正式核准與人工工時是實際輸入，缺失時保留阻擋，不以合成值冒充驗收。

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
