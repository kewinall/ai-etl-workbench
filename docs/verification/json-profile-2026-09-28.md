# JSON 全檔欄位檢查（2026-09-28）

## 範圍

JSON 上傳與命名 profile 已共用嚴格讀取器。**僅隔離 API 驗收，尚未部署正式 Pilot；
不是 JSON Hop／Vertica／QA／Release E2E。** 正式平台仍為已驗收 Excel 的 caf92f4 執行版本。

先前只以前 20 筆找欄位及推論型別，會漏掉後段欄位、後段型別變化或巢狀物件。
Python JSON 預設解析還會讓重複鍵值靜默覆寫，且接受 NaN／Infinity。

## 修改

- `json_profile.py` 掃描支援範圍內的全部資料列，欄位依首次出現順序收集。
- 保留 Decimal 精度、字串前導零及空白，回傳可 JSON 序列化的預覽；不替使用者轉型。
- 缺少 key、明確 null、空字串分開計數，null ratio＝（缺少＋明確 null）／列數。
- 拒絕重複 key（含 Unicode escape 等價名稱）、NaN／Infinity、空欄名、無效 Unicode、
  空資料集／無欄位物件、巢狀值；不自動猜測展開規則或 JSONPath。
- 目前為 UTF-8／UTF-8 BOM 的單一物件或物件陣列；上限 100,000 列、512 欄、
  列數×欄數 2,000,000。超出時明確停止，不悄悄截取前段；上傳大小仍遵循既有政策。
- 上傳與命名分析使用相同掃描結果，只有既有 DECIMAL／NUMERIC 顯示名稱轉換不同。
  原始 byte checksum、row_count、root_shape 與 ALL_RECORDS 範圍有明確標記。
- 陣列順序於解析時保留，**不代表目前已具有來源列序欄、Hop 排序或資料庫輸出順序保證**。
  完整掃描不等於已確認 Naming Contract、execution permission 或 immutable 讀取契約。

## 證據

- 24 項新增單元案例：後段欄位／型別、後段巢狀、精度、缺格／null／空字串、順序、
  重複鍵、錯誤數字／Unicode、BOM、object root 及各規模上限。
- 初次本機 51 passed／4 setup error 原因為測試暫存目錄權限；取得正常測試權限後
  原 55 項組合通過，沒有修改斷言繞過。再加入極端 exponent 拒絕案例。
- 隔離完整回歸初次 1726 passed、106 skipped、1 warning（39.57 秒，exit 0）；
  skips 為 opt-in 原生／HTTP／Windows 等驗收，未列為通過。
- 真實隔離 HTTP：9 passed（0.97 秒）。包括 CSV／Excel 原精度回歸、JSON 後段欄位及
  缺值統計、重複 key／NaN／無效 Unicode／極端 exponent 回應 422 而非 500。
  使用合成上傳，模型與 ETL 派發關閉，沒有新增真實模型請求或 Vertica 寫入。
- 加入 HTTP 案例後最終完整回歸：1726 passed、111 skipped、1 warning（39.40 秒，exit 0）；
  增加的 5 個 skip 是上述另行通過的 opt-in HTTP 案例。來源發行檢查另 1 passed。

## 下一步

1. 加入版本化 JSON 讀取契約與 managed-upload 指紋確認；先支持明確平面來源，
   巢狀／JSONPath 選擇不猜測。契約改動必須產生 revision 並使下游核准失效。
2. 以固定 Apache Hop 版本做原生 JSON Input 行為驗證，再接新版本 specification、
   typed staging、QA context、SDM 及可攜重播，不能直接沿用 CSV／Excel 的解析證據。
3. 最後用全新合成案例完成真實模型至正式 Release；不改既有 20 案分母或原 Excel 交付。

人工基準仍未量測。第 5–7 階段未完成；**尚未持久化至 knowledge-workspace**。
WS-0007 接手者需同步本工程證據、已驗收 Excel 交付及上述具體下一步。
