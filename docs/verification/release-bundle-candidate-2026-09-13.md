# 版本綁定候選 ZIP 封裝核心

## 實作與邊界

新增 `backend/app/release_bundle.py`，不取代或呼叫舊 `release.py`，未接入 API、Worker 或下載入口。既有 Release HTTP 限制保持不變。

- 接收五種明確指定的產物位元組：HPL、HWF、DDL、SDM、PARAMETERS。拒絕缺漏、重複與未知種類，不搜尋歷史產物。
- 每件產物核對 Run、Specification、Naming 指紋與實際內容 SHA-256。
- ZIP 內使用固定相對名稱，不接受呼叫者提供路徑；不讀寫磁碟、不覆寫舊檔。
- 每件上限 16 MiB，總輸入上限 32 MiB。空產物與可變 bytearray 拒絕。
- 固定排序、時間與權限，於同一執行環境可重現。跨 zlib 版本的壓縮位元組一致性未驗證。
- manifest 精確列出五個 ZIP 成員的內容指紋與大小，不以自我參照方式計算自己的 checksum。回傳的 manifest checksum 為 ZIP 中實際 JSON 位元組的 SHA-256。

輸出始終為 `CANDIDATE_NOT_RELEASED`、`portability=NOT_VERIFIED`、`qa_passed=false`、`release_ready=false`。呼叫者提供的指紋不等於權威核准；後續仍須由 Controller 從已核准版本解析產物，接上可攜性掃描、QA 與人工核准。

## 本輪驗證

- 候選封裝及既有 HTTP Gate：18 passed（0.86 秒）。
- 安全後端整批回歸：438 passed、74 skipped（5.26 秒）；排除 legacy test_api.py，關閉資料庫整合與原生 Hop 測試旗標。
- 驗證相同輸入反向排列仍產生相同封裝、ZIP CRC、固定成員集合、manifest 內外一致、各成員大小與指紋、錯誤內容與版本拒絕、容量上限。

測試內容是記憶體中的合成位元組，不是真實 HPL／HWF／Excel。没有產生或交付正式 ZIP，沒有模型呼叫、Vertica 寫入、資料遷移或服務開關變更。

## 後續必要工作

真實 SDM Excel／HWF 產生、參數化與內容可攜性檢查（包括 XLSX 內嵌內容）、權威核准解析、QA 證據綁定、不可變 artifact 保存與正式 Release API 尚未完成。完整 P0–P3 驗收仍未達標。
