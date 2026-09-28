# Excel SDM 與可攜重播工程驗證（2026-09-28）

## 判定

完成 Excel 文件內容與受控重播路徑的程式接通；**不代表 Excel 真實模型／Vertica／Release E2E 通過**。
未部署正式服務、未執行正式 ETL、未重播既有交付、未新增資料庫 migration。
人工基準依操作者决定保留「未量測」，工時改善率不可用。

## 變更

- SDM V4 帶入已驗證的 Excel 讀取契約與來源／Profile／契約指紋，不帶 upload ID、路徑或來源資料。
- 規則頁逐欄說明工作表、標頭、空白列、缺格、額外欄位、公式、文字空白及型別失敗政策。
- 契約或來源指紋變更會拒絕舊規格；即使新版規格有效，也拒絕前一讀取政策的 XLSX 文件。
- 可攜 worker 使用既有完整檔案型別驗證及私有 `source.xlsx` 副本，固定 `SOURCE_XLSX` 參數。
  CSV 單來源、多來源與列序路徑不改格式，不新增重試或 DROP 權限。
- 可攜證據 V4 必須明確綁定 XLSX；Release offer 再比對已執行來源格式及規格的內容指紋。
  CSV proof、錯誤格式、跨來源模式及重新計算 checksum 後的竄改均不能替代 Excel 證據。

## 已執行驗證

| 驗證 | 結果與範圍 |
|---|---|
| SDM 與既有 renderer／列序文件 | 22 passed |
| 新舊格式 proof、重播編排、固定 Git 版本相容性與 Excel SDM | 38 passed；隨後擴充重播 Excel 正反例為 4 passed |
| 完整隔離後端／PostgreSQL | 1675 passed、105 skipped、1 warning，36.07 秒，exit 0；隔離容器正常停止、volume 保留 |
| 真實 Apache Hop 2.12 HWF → HPL | 4 passed，15.87 秒；CSV／XLSX 各成功與缺檔案例；無網路、Dummy sink、無資料庫 |
| 原生 Excel 成功案例 | 3 筆來源經篩選／聚合後目標讀取 2 筆，workflow 完成且 exit 0；缺檔 exit 非 0 且無完成證據 |
| CSV V1／V2／V3 SDM 相容性 | 與固定 commit `16382fef797acdcab4593a9c5a967172cfcdd42b` 的 candidate 及全部儲存格內容相同 |
| 文件視覺檢查 | 既有 deterministic renderer 產出合成候選文件，再以 Spreadsheets read-only import/render 檢查欄位、規則與指紋區；無截斷，未改寫 workbook |

重播編排測試使用真實 staging 檔案但替身 DB／engine，不能算真實可攜資料庫驗收。
完整測試的 skipped 不算通過；原生工作流程及 Git 相容性另外實跑。
合成文件及圖片僅放於本機暫存，不納入交付或 repository；沒有替換平台 renderer 或新增套件。

## 接續工作

1. 將 SA 的 Excel prompt 一致接入版本化 offer、journal、gateway 與本機模型 worker；保留 CSV 相容性。
2. 隔離網站部署驗證規格、節點、QA、文件與交付操作，再建立全新 Excel 合成案例。
3. 保存真實 SA／Developer／Hop／Vertica／QA 與隔離資料庫 HWF 重播證據，才進行正式 Release 核准。
4. 維持階段 5–7 未完成項目：JSON／資料表來源、全站功能對照、報告分頁、可靠 Worker 與部署／還原邊界。

本次尚未持久化至 knowledge-workspace，既有寫入限制不繞過。允許寫入的接續工作應僅同步
WS-0007 的工程證據連結、project commit 與上述下一步，不公開機密或執行資料，也不覆寫其他專案。
