# 規格驅動 HPL 候選編譯器

## 交付與實測

- `backend/app/hpl_compiler.py` 每次重新驗證 Run、Specification、NamingContract，才由確定性程式產生 HPL；不讀取模型 XML、不呼叫模型、不寫入資料庫。
- CSVInput → FilterRows → SortRows → GroupBy → SelectValues → TableOutput；Filter false 明確導向 Dummy discard。無固定前十筆／自動計算欄位。
- 使用 `${SOURCE_CSV}` 與邏輯連線 `etl_target`，產物不內嵌來源路徑、資料或 credentials。Filter 常數按原規格保留，尚須納入最終交付內容審查。
- 命名、規格 checksum 寫入流程描述；回傳 HPL SHA-256。相同輸入輸出相同，測試不改動傳入快照。
- 數值使用 Hop BigNumber 保留十進位型別；COUNT_ROWS 與 COUNT_NON_NULL 分別使用原生 COUNT_ANY／COUNT_ALL，不混用。
- SQL UNKNOWN 排除以明確 IS NOT NULL guard 表達，IS NULL predicate 不附加矛盾的 guard；實際列處理仍待驗證。

2026-09-13 結果：46 項規格／編譯測試通過；Apache Hop 2.12 原生載入編譯候選成功（7 transforms／6 hops），原生欄位傳播確認 category:String、total_amount:BigNumber、row_count:Integer。Hop 重新序列化後保留 SUM／COUNT_ANY、group key、Filter 常數、null guard 與真假路徑。另四項 metadata 正反例全部再次通過。

本次合成候選 SHA-256：`8e0f92a116817607678449e1e65a23091604d7d4a9018500239253c7ec00fd13`。每次測試建立新的合成 Run UUID，所以跨次測試的 checksum 可不同；同一組輸入的確定性另由單元測試驗證。

## 重現

repo 根目錄 PowerShell：

```powershell
./scripts/test-hop-compiler.ps1
./scripts/test-hop-metadata.ps1
```

需既有 Windows Python venv、WSL RockyLinux9 與本機 `apache/hop:2.12.0` image。測試只建立 `outputs/hop-compiler/candidate.hpl` 合成產物；容器無網路、唯讀掛載、結束即移除，不改平台服務。

## 不可誤認為已完成的部分

回傳 `HPL_CANDIDATE_NOT_EXECUTABLE`、`execution_authorized=false`，不是已核准／可 release 產物；尚未接到網站、API 或 Worker。

仍須：

1. 對實際 CSV bytes 驗證編碼、BOM、header、欄位數與 REJECT／IGNORE 政策；目前 XML 不足以執行這些政策。
2. 原生資料列驗證日期／timestamp 格式、null 與空字串、decimal、SUM 全 null、大小寫 grouping 等語意。原生 metadata 通過不表示值正確。
3. 規格持久化與人工核准、實際 connection metadata 綁定、HWF／DDL 編譯與控制器接線。
4. Hop → Vertica 標準答案 QA → SDM → 人工核准 Release；四情境及 P3 評估。

沒有新增 Copilot 請求、Vertica 連線／寫入或平台執行權限。P0–P3 仍未完整達標。
