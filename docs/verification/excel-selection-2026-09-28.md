# Excel 工作表與標頭確認驗收（2026-09-28）

狀態：已部署來源選擇、Task 保存與回讀；**尚非 Excel Hop／Vertica／Release E2E**。

## 問題與實作

原上傳直接使用第一張工作表、第一列標頭，空白欄名自動補名，重複欄名經
dict(zip(...)) 可能覆蓋值。現在 Excel 上傳只列工作表，不替使用者作選擇，
單一工作表也須按「解析並確認此工作表」才能建立 Task。

新增 `POST /api/task-sources/{upload_id}/excel-profile`，僅讀取已管理上傳的
XLSX。輸入 checksum、size、worksheet、header_row；不接受任意檔案路徑。
在已核對 SHA-256／大小的 bytes 上解析，worksheet 必須存在，標頭列限
1–1000，現階段最多 512 欄、20 筆樣本；空白／重複標頭會要求修正。
工作簿在成功／錯誤路徑皆關閉。

回應包含 `excel_selection_v1`，綁定上傳識別、原始 bytes 指紋、大小、工作表、
標頭列、推論欄位及 profile checksum，scope 明示 `INPUT_SELECTION_ONLY`。
這不是執行授權、全檔型別驗證或數位簽章。Task 建立時由伺服器重新解析
並比對；新 Run 的來源 preflight 使用已驗證的同一 byte snapshot 再核對，
不重新開啟檔案取另一份 bytes。命名 profile 沿用同一選擇與欄位。

網站提供工作表下拉、標頭列、重新解析、錯誤說明。変更選擇後，舊確認立即
失效；解析等待時鎖定來源與建立／取消操作。只保存選擇 metadata，不把
原始 preview sample_rows 帶入 Task。詳情「需求與規格」顯示已保存的工作表、
標頭列及可展開的選擇指紋。舊 Task 未改寫，沒有選擇證據時明示舊版狀態。

## 已執行證據

- 定向後端：**46 passed（1.29 秒）**。含缺少選擇、改欄位／header／checksum、
  缺工作表、空白與重複標頭、不合法 header 型別與任意 path 拒絕。
- 完整隔離 PostgreSQL 回歸：**1530 passed／82 skipped／1 warning（41.74 秒）**。
  略過的原生／實機 opt-in 不計通過；沒有呼叫模型、Hop 或 Vertica。
- 真實隔離 HTTP 三格式上傳與巢狀 JSON 拒絕：**4 passed（0.66 秒）**。
  XLSX 更新為上傳後先確認工作表再檢查欄位，CSV／JSON 契約未放寬。
- 新增多工作表真實瀏覽器測試，初次 **1 passed（5.0 秒）**：
  明細位於第二張表、標頭在第二列，第一張為說明頁；錯誤 header 與重複欄
  都被拒絕。成功 Task API 回讀相同選擇、指紋與欄位，命名 API 只使用
  明細欄位；無確認的直接建立 API 回 422，Run 清單仍空。
- 最終網站完整選跑 **16 passed（22.2 秒）**，含上述實際上傳、metadata
  白名單保存及重新載入摘要；另含專案／CSV／雙 CSV／設定／歷史節點回歸。
  解析等待測試只延後後轉送真實請求，不以 fake response 冒充成功；其他
  既有故障／舊產物 fixtures 的證據邊界沿用原測試。390px 無水平溢出，
  截圖已檢視，保存在 Git 忽略的 runtime-temp，不提交操作資料。
- 部署前唯讀維護檢查通過；API、control-worker、web 已更新，保留既有
  四項 dispatch flags，未改 migration、資料庫 volume 或已核准版本。
- 最終正式指南／集合量測／報告唯讀回歸 **3 passed（19.2 秒）**。
  SQL 前後皆 Run 305、events 2861、歷史 deliveries 24；ready、execution
  enabled。沒有正式模型呼叫、上傳、Run、Hop 執行或 Release；隔離服務已停止。

`frontend/tests/fixtures/excel-selection.base64` 是三張合成工作表的固定 XLSX
測試 fixture（說明、明細、重複欄），由 `test_excel_profile.workbook_bytes`
產生，不包含真實資料或憑證。

## 尚未完成與下一步

本輪只處理新 Excel 來源選擇與確認，不宣稱已完成全部來源支援。
仍需補 Excel formula／null／型別與完整讀取契約、SA／Developer 支援、
deterministic compiler 及原生 Hop／Vertica／QA／可攜 Release 驗收。
既有 Excel Task 的明確補正與新 revision 操作也尚待接通，不回填虛構確認。
JSON 正常入口與結構契約、CSV 標頭等跨 profile 一致性、資料表／範例來源
完整流程仍保留在原範圍。另須驗證切換 NORMAL／External／Flex 後的來源
格式一致性；不得把已上傳 XLSX 只改類型文字就當作 CSV／JSON。

下一步從 `sa_contract.py` 的來源限制與 source preflight／staging／compiler
契約對照，確認 Excel 要進入同一受控 Run 所缺的完整格式條件，補齊後再
進行原生測試，不繞過任何既有 QA／Release gate。

人工基準仍依操作者決定未量測。knowledge-workspace 本機目錄不存在，
本次證據已保存在 project repository，但尚未持久化至 knowledge-workspace。
