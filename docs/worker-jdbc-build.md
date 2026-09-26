# Worker JDBC 建置前置條件

Worker 不再從 `local/vertica:25.3.0-rpm` 複製驅動。
操作者須依授權取得 JDBC JAR，放在獨立目錄並命名為 `vertica-jdbc.jar`。
不將 JAR、憑證、資料或 .env 提交 GitHub。API 與一般控制平面建置不需要 JDBC。

## 目前驗證基準

- 檔案來源：既有 Pilot 的 Vertica 25.3.0-2 安裝包內 JDBC。
- SHA-256：`849c0dcf76e72e9022cac6bad1f1141dba2b6468369a14f29c873347d465622f`。
- 此值為本機已使用檔案的實測值，不冒稱官方簽章或下載站校驗值。
- 取得方式可以是合法取得的 client package，不要求存在本機 Vertica image。
- 本輪不升級驅動版本，也不宣稱其他版本相容；技能文件的 24.4.x 範圍不代替 25.3 實測。

## 建置（WSL/Linux）

從 repository 根目錄執行，將目錄改成實際 JDBC 所在的絕對路徑：

```sh
export WORKBENCH_JDBC_DIR=/absolute/path/to/jdbc-directory
sha256sum "$WORKBENCH_JDBC_DIR/vertica-jdbc.jar"
docker compose -f deploy/compose.yml --profile pilot-execution build pilot-hop-worker
```

未指定目錄時預設 `runtime-temp/jdbc`（Git 忽略），缺少檔案時 Worker build
必須失敗，不會偷偷從另一個 image 或網路下載驅動。需要支援 named build contexts
的 Docker BuildKit／Compose；本次實際 Docker 29.6.2 環境另有驗證紀錄。
本次 Compose 為 5.3.1；未宣稱其他版本已驗收。

僅建置驅動校驗階段：

```sh
docker build -f deploy/Dockerfile.backend --target vertica-driver \
  --build-context "vertica-jdbc=$WORKBENCH_JDBC_DIR" .
```

變更驅動應獨立審查來源、版本、SHA-256 與真實連線驗收；不要因 checksum
不符就改成任意 hash 以通過建置。刻意升級可用 Docker build arg
`VERTICA_JDBC_SHA256`，但不得沿用舊驗收結果。

## 回復

建置不會重啟既有容器、修改資料庫或執行 ETL。若新 Worker 驗證失敗，保留
既有運行 image/container；不重新派送已核准 Run，不刪除 volume。
`compose.portability.yml` 的測試資料庫仍使用本機 Vertica image，該前置條件
與 Worker/JDBC 解耦是兩件事，尚未宣稱整套測試資料庫可攜。

## 2026-09-26 實測

- 正確 JAR：獨立 `vertica-driver` target 建置成功。
- 全零 SHA-256：實際 build 非零結束，顯示 checksum mismatch。
- 缺少 context 目錄與目錄內缺少 JAR：均實際 build 非零結束。
- Compose `pilot-hop-worker` 完整建置成功；沒有重啟既有服務。
- Worker image ID：`sha256:0308e1bac268669a9ed4d873fcbc6280ff88bb3905a471f8c1b9f91dc613c589`。
- 新 Worker 執行 `test_hop_adapter_native.py`：2 passed（6.04s），
  包含正常與錯誤數字資料；`--network none`，目標 Dummy，不接觸 Vertica。
- 控制平面隔離回歸：848 passed、23 skipped、1 warning（20.17s）。
- 這些證據證明驅動供應檢查、Worker 建置及 Hop adapter 回歸，
  不是新版本的真實模型／Vertica／Release 整合驗收。
