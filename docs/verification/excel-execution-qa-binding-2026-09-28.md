# Excel 受控準備與 QA 證據綁定（2026-09-28）

狀態：程式及下列驗證通過，**尚未部署至正式 Pilot，也不是 Excel／Vertica／Release 全鏈驗收**。
沿用既有 Task／Run／核准與單次領取，不另建執行系統、不使用模型決定權限。

## 實作

- `EtlSpecificationV4` 現可經既有規格 validate、compile-preview、save、approve 與
  editor-context API；編輯綁定包含已確認的 Excel 三重指紋，不退回 CSV V1。
- `execution_sources` 只對 V4 接受完整已確認 XLSX 契約，保存 `source_format=XLSX`。
  核准使用 `hop-single-attempt-v4`；既有 CSV 單／雙來源核准格式保持不變。
- `execution_preparation` 先驗證來源契約，再將同一份已驗證 bytes 全檔檢查並暫存為
  `source.xlsx`，不轉 CSV。檔案 I/O 後重讀規格與核准；失效即拒絕並清除本次副本。
  原始上傳不刪除；暫存本身不代表執行授權。
- 格式、來源 checksum 與 HPL checksum 綁入 reserve 及 `begin_external_write`。
  移除或改寫格式不准領取／開始；同一 consent 只能消耗一次，不自動重試寫入。
- 最後使用前檢查固定 filename、範圍、symlink／reparse、大小及內容 checksum。
  Hop argv 只允許單一 XLSX 的 `SOURCE_XLSX`；混用雙來源或任意參數名稱會拒絕。
  候選交付參數範本同步使用 `SOURCE_XLSX`，但這不是可攜重播通過證明。
- QA 重新檢查同一來源 bytes、selection、全檔型別與契約，產生專用 context v14。
  ExcelInput 不再被 CSV-only 檢查忽略：核對 POI、唯一 required file、sheet／startrow、
  空白列、錯誤處理、format／precision／trim／repeat，以及 checksum-bound 輸出選項。
  Context 必須包含來源格式與目標 DDL claim 證據，不允許只提供空來源清單。
- QA prompt v11 僅套用 Excel，明示 preflight 不等於 Hop 轉型或 Vertica 成功；
  API offer、journal、native bridge、gateway 使用同一 prompt fingerprint。
  `PASS` 仍是建議；deterministic FAIL 不能被模型覆蓋。
- CSV 原有 prompt v10、QA context v3／v6／v5／v13 與編譯輸出未追溯改寫。

## 驗證與發現

1. 初批格式綁定／檔案／argv／CSV 相容性：52 passed。
2. 原生一般 CLI 的 XLSX／CSV 成功與缺檔：4 passed，無網路、Dummy sink。
3. 第一輪完整後端出現 3 failed／1611 passed：真實規格 API 仍只接受 V1–V3，
   Excel V4 保存回 422。修正 API union，未將測試改成略過 API 或只測 compiler。
4. Excel runtime options 與現有 QA 選項：33 passed；完整 QA context、提示詞、
   證據變更／遺漏、來源檔變動與不可覆蓋 FAIL 等選跑：93 passed。
   此處模型回應為明示測試替身，不是真實模型驗收。
5. 最終完整隔離 PostgreSQL 後端：**1659 passed／100 skipped／1 warning，36.56s**。
   真實 API／DB 驗證規格預覽、編輯綁定、保存核准、準備期間核准失效、一次領取、
   格式變更阻擋及最後 write-start gate。該測試只記錄控制資料庫狀態，沒有呼叫外部 executor。
   隔離服務正常退出並停止，volume 保留；未使用正式 DB／credentials。
6. 原生 Java 啟動器測試初次把六個 plan stages 誤作完整節點數而失敗；實際 HPL
   另有必要的 `discard`，共七個節點。依實際 graph 修正斷言，另核對 discard 1／target 2，
   未刪除完整節點檢查。
7. 最終 **10 passed／22.63s**：四項 Excel 一般／正式 Java launcher 成功與缺檔、
   兩項 CSV 原生 CLI、四項 Git 固定版本相容性。Excel 成功路徑七個節點證據完整、
   篩除 1 筆／輸出 2 筆；缺檔非零退出、來源節點報錯。容器無網路、資料為合成、
   TableOutput 僅在此測試替換 Dummy，不宣稱 Vertica 寫入或完整 ETL 結果驗收。
8. CSV HPL／HWF／SA 比較固定 commit `25120fc520cd14d01004e20aa9a8a1718fe3ddc5`；
   CSV QA contexts／prompt 比較 `7521a9ab97396499e093731654595509df87748b`，完整內容一致。
   後端容器中略過的四項 Git 測試及六項本輪 CLI 測試已在上述 Windows／WSL 測試實跑；
   其餘 skipped 不視為通過。
9. 正式 `/api/ready` 唯讀回應 ready、execution enabled。本次沒有正式部署、模型呼叫、
   Vertica 寫入、既有 Release 重播或資料庫 migration。

## 尚未完成與下一步

- `release_replay_worker` 仍只做 CSV staging；`release_portability`／`release_store`
  尚須新增 XLSX 格式綁定與 proof，SDM 須帶入 Excel selection／政策語意。
  先接通這些路徑並驗證錯誤格式／缺檔，不能為了過關省略可攜驗收。
- SA Excel 專用 prompt 需一致版本化至 offer／journal／native worker；本輪只處理 QA。
- 之後部署隔離網站、核對規格編輯／歷史／節點／QA 顯示，再做新的合成案例真實
  SA→Developer→Hop→Vertica→QA→SDM→Release；每一步保存真實證據，不重跑既有交付。
- QA context v14 目前為契約／替身驗證，尚無新 Excel 真實資料庫結果或真實 QA 模型。
- JSON、資料表與受控範例來源、全站完整功能對照及第 6／7 階段其餘項目仍追蹤在階段索引。

人工基準依操作者決定維持未量測，改善率不可用；第 5 階段及整體目標仍未完成。
已唯讀核對 GitHub knowledge-workspace 的 WS-0007，內容仍落後於實際 repository；
既有遠端寫入審查限制不繞過，**本次尚未持久化至 knowledge-workspace**。
接續具允許寫入權限的工作應將此證據連結、最新 project commit 與上述下一步更新到
WS-0007／CURRENT／handoff，保留其他專案狀態及既有歷史，不複製執行資料或機密。
