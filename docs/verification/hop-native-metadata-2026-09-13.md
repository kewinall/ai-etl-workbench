# Hop 原生 metadata 驗證基礎

## 已驗證範圍

2026-09-13 使用本機既有 `apache/hop:2.12.0` image 的 Java 17 與 Hop 原生 `PipelineMeta`，不是以一般 XML parser 代替 Hop 載入。新增工具不建立 Pipeline execution engine、不連線資料庫、不呼叫模型，沒有更動平台派發設定。

驗證容器使用 `--network none`、`--pull never`，僅唯讀掛載工具與合成 fixture。不存在外部來源資料或 credentials 掛載。容器結束即移除，既有平台容器不重啟。

## 重現

在 repo 根目錄的 PowerShell 執行：

```powershell
./scripts/test-hop-metadata.ps1 -Distribution RockyLinux9
```

需要既有 WSL、Docker 及上述 image；工具不自動下載、安裝或啟動平台服務。固定使用 Linux amd64 Hop classpath。

| 案例 | 實測 | 意義 |
|---|---|---|
| minimal | exit 0；2 transforms、1 hop | 兩個 Dummy 節點由 Hop 原生 metadata 載入 |
| missing-plugin | exit 2 | 不存在的 transform plugin 不可被當成成功 |
| invalid-edge | exit 2 | 不存在的下游節點遭拒絕 |
| doctype | exit 2 | XML 外部 entity 在進入 Hop 前被拒絕 |

四項均 PASS。PASS 代表預期的接受／拒絕，不代表四條 ETL 執行成功。

初次探測僅載入 `lib/core/*`，Hop 初始化缺少 Java 類別。比對容器內 `hop-run.sh` 後補上原有 `lib/beam/*` 及 Linux SWT classpath，未新增套件。離線容器本機名稱解析另以固定 loopback hosts entry 排除，不開啟網路。

## 限制與下一步

- 這是開發驗證工具，尚未整合成平台 API／Worker 的 release gate。
- minimal 為合成測試 HPL，不是 EtlSpecificationV1 編譯器的輸出。
- 尚未驗證 CSV 型別轉換／額外欄位政策、Filter null semantics、GroupBy 聚合結果、TableOutput metadata 或真實寫入。
- 不宣稱 metadata loader 可證明語意、執行安全或任意第三方插件安全；不得直接將此 CLI 暴露為使用者任意檔案執行入口。
- 下一步須由已驗證的 Specification 與 NamingContract 產生原生 HPL，增加對應插件與流向測試，再做 Hop／Vertica 標準答案比對。
- P0–P3 仍未完整驗收；本次沒有新增 Copilot 使用量。
