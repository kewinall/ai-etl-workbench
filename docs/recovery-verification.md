# 隔離復原副本驗證

`python -m app.recovery_verify` 是復原後的檢查工具，不是備份、還原、修復或
Release 核准工具。必須先建立隔離 PostgreSQL 與完整私有副本。它不派發模型
或 ETL，不會將結果寫成平台核准，也不代表 HTTP 或異機復原已完成。

## 前置條件

### 私有可攜副本封裝

`python -m app.recovery_export --dump-checksum <verified-sha256>` 封裝已事先
停止寫入、配對驗證的復原副本，不負責為 live system 建立一致性 snapshot。
需要 `WORKBENCH_RECOVERY_EXPORT=private-copies-v1`，以 network-none helper
掛載 `/copies/{secrets,uploads,artifacts,outputs}` 與 `/snapshot.dump` 為唯讀，
`/backup` 為本機私有備份目錄。禁止使用 repository、公開分享或發布目錄。
工具建立新的 UUID 子目錄，不覆寫現有目錄，包含 DB dump、四份 tar 與
最後寫入的 manifest。逐檔重讀 archive 比對，並保存五份內容的 SHA-256。
任何沒有完整可讀 manifest 的中斷輸出不可使用；工具不自動清除它。

**封裝含未另行加密的金鑰與私有資料，不能上傳 GitHub 或公開傳送。**
檔案系統存取控制由備份目的地負責；若需離機，另行決定加密及保管政策。
這是可攜封裝，不等同 offsite、完整角色權限或從封裝實際還原的驗收。

### 從封裝還原檔案

`python -m app.recovery_unpack --package /package --destination /restored`
先檢查五個固定成員的大小／checksum、四份 tar 的全部成員，再解包。
只允許一般檔案與目錄，拒絕 traversal、絕對路徑與連結；四個目的子目錄
`secrets/uploads/artifacts/outputs` 必須已存在且全空，不可重用正式卷。
以 runtime UID 10001 執行；新 Docker volume 根目錄預設 root 擁有，應由
launcher 在確認空卷後只調整新卷根目錄擁有者，不能遞迴改寫既有資料。
來源 package 必須 readonly 且不被其他程序修改，helper 使用 network-none。
本工具不恢復 PostgreSQL。DB dump 另以 `pg_restore --exit-on-error
--single-transaction --no-owner --no-privileges` 還原至新 restore_ DB；這不保存
原始 roles／ACL。任一步驟失敗不可繼續宣稱成功，也不要直接覆盖部分解包。
接著將新檔案卷改 readonly 執行 `app.recovery_verify --http`。

1. 使用與備份相容的 API image 和 PostgreSQL 版本。保留 migration ledger，
   不手改 checksum 或跳過 migration 檢查。
2. 資料庫容器使用 `--network none`，無 host port，資料庫名稱以 `restore_`
   開頭；不得把正式 DB volume 掛入還原容器。
3. 完成 DB 還原，並複製該備份對應的 secrets、uploads、artifacts、outputs。
   這些副本包含私有資料，禁止加入 Git／公開 artifact。
4. verifier 只共用隔離 DB 的 network namespace，全部副本 readonly，root
   filesystem readonly。不要啟動 Worker。操作者須檢查 mounts 確為副本；
   工具不能靠 mount path 證明 volume 的來源。

## 執行契約

以下為參數契約，請代入已確認的隔離容器與副本 volume 名称：

```text
docker run --rm --read-only
  --network container:<network-none-restore-container>
  --entrypoint python
  -e DATABASE_URL=postgresql://workbench@127.0.0.1/restore_<name>
  -e WORKBENCH_RECOVERY_VERIFY=isolated-copy-v1
  --mount type=volume,src=<copied-secrets>,dst=/run/workbench-secrets,readonly
  --mount type=volume,src=<copied-uploads>,dst=/app/runtime-temp,readonly
  --mount type=volume,src=<copied-artifacts>,dst=/app/hop-project,readonly
  --mount type=volume,src=<copied-outputs>,dst=/app/outputs,readonly
  <verified-api-image>
  -m app.recovery_verify --project <project-uuid> --cohort <cohort-uuid>
  --expected-releases <expected-count-1-to-20>
```

上述以多行表示參數，不是跨 shell 通用可直接貼上的指令。請保留實際執行的
image digest、備份 checksum 與去識別化輸出；不可把密鑰放入命令列。

工具拒絕非 loopback、非 restore_ DB、含密碼／query override 的連線字串，
需明確 opt-in，檢查 IPv4／IPv6 路由與唯讀 mounts。這是誤用防護，不是對惡意
操作者的隔離保證。DB 內部驗證需要 SELECT FOR UPDATE，因此不能將 transaction
設成 PostgreSQL read-only；服務程式不寫入，但仍需停用其他寫入者。

成功 exit 0、輸出 PASS 與數量；失敗 exit 1，避免輸出可能含密碼或私有路徑
的原始 exception。失敗時先檢查隔離環境、mounts、版本及備份，不要重新執行
ETL、改寫核准或放寬校驗。缺失不能當成零。完成後停止隔離容器，保留或依
獨立保留政策處理副本；本工具不自動刪除資料。

## 驗證範圍

### 全卷檔案比對

`python -m app.recovery_files --source /source --restored /restored` 要求兩側
皆為 readonly mounts，逐檔 SHA-256 比對相對名稱、內容與空目錄，只輸出
數量，不輸出檔名、內容或個別機密檔案的雜湊。相同根目錄、symlink、特殊
檔案、無法讀取目錄、讀取中變動均拒絕，不跟隨連結離開指定範圍。
使用 network-none helper、兩個已確認來源不同的 volumes 與 readonly root。
工具不建立或刪除備份，不驗證 modes、ACL、owner、timestamp 或硬連結關係。
唯讀掛載不能阻止其他程序改寫來源；一致性備份仍須另行協調停寫與 DB 時點。
兩側內容一致只證明本次掃描結果，不是跨檔案的原子快照或異機復原證據。

在上述 CLI 加上 `--http`，可在原隔離檢查通過後自動啟動短生命週期的
Uvicorn loopback TCP server，完成 HTTP 檢查並關閉。它使用實際 `app.main`，
四項派發旗標固定 false、不啟動 Worker，僅允許量測與 Release download 的
GET 路徑；其他方法與路徑拒絕。啟動最多等待 5 秒、關閉最多等待 10 秒。
HTTP 與 service-layer 案數需一致，且 Run／effort 事件數不得改變。
沒有 `--http` 時仍保留原 service-layer 檢查。此短生命週期 server 不取代
部署 entrypoint、migration readiness 或操作網站的完整復原驗收。

另有 `app.recovery_http.verify_http(base_url, project_id, cohort_id, expected_releases)`
供已隔離的 API 使用。它只送 GET，關閉環境 proxy、redirect，核對 20 案與
實際下載的標頭、checksum、ZIP；不負責建立隔離或啟動服務。呼叫前仍須
核對無外部網路、全部副本及派發關閉，並在呼叫前後獨立核對資料庫事件。
`transport` 參數僅供合成測試；使用 mock 的結果不可標為真實 HTTP 驗收。
最新 loopback TCP 實测與限制見 [第 7 階段](verification/stage7-current-status.md)。

- 解密已還原的 secret entries，只檢查非空，不輸出明文。
- 固定 20 案集合的現有 Release gate 和 expected release count。
- 實際 download service 的 checksum、六個 ZIP 成員及 CRC。
- Run event 數量前後不變。

不證明：所有 DB 表 byte-for-byte 一致、全部歷史產物完整、roles／ACL、
HTTP／瀏覽器下載、異機／離線備份、重啟中斷寫入或人工工時改善。
