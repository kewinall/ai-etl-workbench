# 來源型別建議修正與驗證（2026-09-28）

狀態：共用推論修正已部署；不是 Excel／JSON 的 Hop E2E 驗收，整體目標未完成。

後續：[Excel 選擇流程](excel-selection-2026-09-28.md) 已取消自動採用第一張
工作表；現在需明確選擇／確認後才回傳欄位並允許建立 Task。下方為本次
型別修正當時的驗證，工作表缺口以該後續文件的最新證據為準。

## 已證明的問題與修正

原上傳 `_field_type` 將前導零整數判為 BIGINT、浮點可解析值一律建議
DECIMAL(18,4)，文字按字元而非 UTF-8 bytes 計長，且封頂 4000。
命名 profile 另有一套不同邏輯，會把只有 0／1 的欄位判為 BOOLEAN，
僅用日期正規式而未檢查實際日期。兩者現改用 `app.field_inference`：

- `00123`、帶前導零或前後空白的值保留 VARCHAR 建議，不默默轉型或 trim。
- 0／1 建議 BIGINT；true／false 才建議 BOOLEAN。
- 超出自動 BIGINT 範圍時按 Decimal 精確計算所需 precision／scale。
  一般小數維持至少 (18,4)，需要更多位數時擴充，不為配合固定四位而縮小。
- 遵守現有 compiler 的 precision <= 38、scale <= 18 子集合。
  超出者保留文字建議，不宣稱這是 Vertica 引擎的最大限制。
- VARCHAR 按 UTF-8 bytes 計算，不將長文字偷偷截至 4000／2048。
  超過 compiler 支援長度則要求補正，未自動新增 LONG 型別。
- 無效日期不建議 DATE；原生 Excel 日期／時間可辨識。
- JSON 小數用 Decimal 解析；回傳樣本以精確字串呈現，原始檔案 bytes 與
  checksum 不變。巢狀欄位要求展開規格，不以 Python 字典字串當一般文字。
- 已明確宣告的型別與既有 immutable Naming Contract 不重寫；上傳使用
  DECIMAL、命名 profile 使用同義 NUMERIC，precision／scale 相同。

依 Vertica SQL skill 查核的離線官方文件是 **24.4.x**：Character 長度按
bytes 的說明見 PDF p.2206，型別表與 64-bit integer 見 p.2424，Exact Numeric
家族見 p.2455。這是文件依據，**本輪沒有執行 Vertica SQL／Hop**，不把它
當作目前 25.3 測試環境的原生執行證據。compiler 子集合以實際程式為準。

## 實際驗證

1. 初次定向測試 35 passed／2 setup errors，將超長參數案例明確命名後，
   同批 36 passed（0.18 秒），沒有刪除長字串拒絕案例。
2. 首次隔離全後端 1515 passed／78 skipped（34.38 秒）。
3. 補充 Decimal 極小數與實際 HTTP 測試後：4 項 HTTP + 30 項型別測試
   **34 passed（0.79 秒）**。HTTP 指向明確限定的隔離 5195，不使用 mock：
   CSV、JSON、XLSX 都回傳 VARCHAR(32)、DECIMAL(26,6)、VARCHAR(60)，
   样本保留 `001`、完整金額，檔案大小與 SHA-256 相同；巢狀 JSON 回 422。
   XLSX 使用精確文字儲存金額，不宣稱能恢復來源 Excel 已捨入的 numeric cells。
4. 最終隔離全後端 **1516 passed／82 skipped／1 warning（34.53 秒）**。
   skipped 包含 4 項上述已另跑的 HTTP 測試，以及其他需原生工具／既有
   evidence／PowerShell 的 opt-in 測試。不能將 skipped 計作通過。
5. 新 API 下專案／單雙 CSV 建立／節點／來源範圍瀏覽器回歸：
   **4 passed（9.7 秒）**。
6. 正式部署前只讀維護檢查通過，確認無待執行工作及外部 Worker；僅更新
   API、control-worker，保留四項原有派發設定，未改 DB 或 migration。
   正式容器直接執行合成推論斷言通過，ready=true。
7. 正式指南、集合量測、報告唯讀回歸：**3 passed（19.2 秒）**。
   部署前後 SQL 皆為 Run 305、Run events 2861、歷史 deliveries 24。
   沒有新模型呼叫、Hop 寫入、正式上傳、Run 或 Release。隔離服務已停止。

## 尚未完成與接續位置

推論仍是樣本建議，不是全檔型別證明、主鍵證明或核准的 Naming Contract。
Excel 多工作表目前上傳自選第一張，尚缺明確選擇／補正契約；重複標頭、
抽樣範圍與跨 profile 一致性仍需收斂。JSON 的正常建立頁入口及結構契約也
尚未完整接通。下一步檢查 `task_uploads.py`、`source_profiler.py` 與建立表單，
補 worksheet／header／結構確認及版本綁定，再推進 source preflight、compiler、
Hop／QA／Release 的完整支援，不以這次型別修正取代原範圍。

人工基準依操作者決定保持未量測。knowledge-workspace 本機目錄不存在，
本次證據保存在專案 repository，尚未持久化至 knowledge-workspace。
