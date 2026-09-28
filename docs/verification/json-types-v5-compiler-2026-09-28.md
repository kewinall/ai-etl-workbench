# JSON 全檔型別與 V5 原生編譯驗證（2026-09-28）

## 判定

JSON 已新增全檔型別檢查、Gate／暫存副本接線，以及獨立 `EtlSpecificationV5` 的
HPL／HWF 候選編譯。真正編譯出的篩選／彙總 HPL 已以原生 Hop 驗證固定答案。
**尚未接入 V5 模型角色、規格 API／網站、正式執行授權、QA、SDM、可攜重播及 Release。
沒有部署正式 Pilot，不能宣告 JSON E2E 或第 5 階段完成。**

## 實作與界線

- 完整掃描全部紀錄，驗證每一欄的 UTF-8 位元組長度／NUL、布林、ISO 日期／秒精度
  timestamp、整數範圍／小數、Decimal precision／scale；保留 int／Decimal 原值，不轉 float。
  缺 key 與 null 保留 NULL，空字串不當成 NULL、數字不隱含轉字串、字串不 trim。
- 錯誤只回傳錯誤代碼與 1-based 紀錄／欄位座標，不回傳資料值或路徑。
  提供型別時必須完整且均屬既有 compiler subset；不支援型別即使全 NULL 也不通過。
- Gate 及 `stage_json_source` 皆要求完整型別檢查；暫存前重新驗證來源 profile 確認，
  原始／reader 雙指紋與型別 checksum 均保留。只移除 reader 副本的 UTF-8 BOM，
  不改寫上傳來源或重序列化 JSON。沒有確認證據不能取得副本。
- proof 的 `column_types_checked=true` 不等於原生轉換已全數驗證；
  `type_conversion_verified=false`、`execution_authorized=false` 保持明確界線。
- V5 綁定來源、profile、契約三個指紋及既有 Run／Naming 版本；沿用確定性
  Filter／Aggregation／Projection／APPEND 驗證，不接受任意 XML、SQL 或 JSONPath。
- 計畫列出實際三個來源節點：`source_file`（單筆檔名參數）、`source`（JsonInput）、
  `source_columns`（排除檔名欄）。`json_source_file` 為保留內部欄名。
  HPL／HWF 使用明確 `SOURCE_JSON`，不回退 CSV；產物仍為不可執行的候選。
- 執行來源授權目前明確回傳 `JSON_EXECUTION_NOT_READY`，不能因候選編譯成功越過後續接線。

## 已驗證證據

| 範圍 | 最終結果 |
|---|---|
| 型別、契約、profile、副本、規格、原生、CSV／Excel 相容性與來源發行組合 | **139 passed，91.18 秒** |
| 完整隔離 PostgreSQL 回歸 | **1842 passed、131 skipped、1 warning，52.63 秒，exit 0** |

139 項包含 19 項明確啟用的真實無網路 Hop 測試。131 項 skipped 包含另行完成的
JSON 原生／Git 歷史比對及其他須外部環境的 opt-in 測試；不把全部 skips 視為通過。
warning 為既有 Starlette／AnyIO deprecated alias，不是 ETL 成果。

### 原生 Hop

- 全部使用已安裝 Hop 2.12 Worker、無網路容器、唯讀掛載，沒有模型、憑證或 DB。
- JSON 原生日期／timestamp／bool、exact Decimal、BIGINT 邊界、整數型 decimal token、
  字串 `1.0` 的整數讀取、缺值／空字串／全 NULL 列、欄名字面符號及 BOM 副本均重跑。
- V5 三項測試真正呼叫 `compile_hpl`，只把 TableOutput 目的端替換為 Dummy collector，
  其餘來源、Filter、SortRows、GroupBy、Projection 及邊保持編譯產物。
- 固定資料輸出 A／251.75／2、C／201.00／1，精確數值與列順序一致；全部被篩除為零列；
  缺檔必須失敗。這些不是 Vertica 寫入或正式 HWF CLI／Release 重播。
- 原生測試仍明確固定 `HOP_JSON_INPUT_INCLUDE_NULLS=Y`；正式 launcher／可攜環境後續
  必須同樣固定並綁定，不可依賴開發機環境。

### Gate 與相容性

- 真實隔離 PostgreSQL 案例涵蓋「型別建議已確認但資料需要隱含轉換」：斜線日期、
  整數欄空字串、大寫布林字串、混合數字／文字。全部維持 NEEDS_INPUT、未開始寫入；
  保存原輸入核准，未把型別建議當執行成功，也沒有把資料值洩漏至 Gate 錯誤。
- 全檔第 26 筆壞值仍被攔截，型別覆蓋缺漏／超出／不支援及超長／溢位／精度不符均拒絕。
- CSV V1–V3 與既有不可變 baseline 的完整候選結果相同；Excel V4 與前次
  `42eaccb41bd45dbb0af7ba6b817074d65c440b7b` 的 HPL／HWF 結果完全相同。
- 正式 Excel 既有 Release 本輪唯讀確認仍為 RELEASE_READY；未重建正式服務或重跑原寫入。

## 下一步／交接

1. 接通 JSON SA evidence、Developer V5 schema／prompt 與一致的 gateway／journal 版本，
   再接規格 API／網站顯示；缺少角色證據或版本不符仍應拒絕。
2. 完成 V5 原始／reader 雙指紋 reservation、單次執行、JSON null 設定、QA／SDM／
   manifest／HWF 可攜重播，之後才能解除 `JSON_EXECUTION_NOT_READY`。
3. 建立獨立真實 JSON 案例完成角色→Hop→Vertica→QA→SDM→Release，不改原 20 案分母。

人工基準依使用者指示仍未量測；整體七階段目標未完成。
**尚未持久化至 knowledge-workspace**；須同步 WS-0007 的已驗證工程與以上下一步，
不複製上傳資料、私有 runtime IDs 或憑證。專案 repository 文件為本輪接續證據。
