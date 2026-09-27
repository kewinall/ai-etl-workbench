# 隔離復原副本驗證

`python -m app.recovery_verify` 是復原後的檢查工具，不是備份、還原、修復或
Release 核准工具。必須先建立隔離 PostgreSQL 與完整私有副本。它不派發模型
或 ETL，不會將結果寫成平台核准，也不代表 HTTP 或異機復原已完成。

## 前置條件

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
