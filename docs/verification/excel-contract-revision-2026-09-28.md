# Excel 讀取契約補正與網站驗收（2026-09-28）

狀態：已部署契約補正 API 與操作畫面。**不是 Excel 正式 Hop／Vertica／Release E2E**。

## 行為

- 沿用 Task 的 Run revision API，新增 `excel_input_contract_v1`，不另建 Task 系統。
  更新的是來源讀取政策，不允許藉此切換未確認工作表、標頭或換檔。
- 先檢查舊版 checksum、可補正狀態、最新設定與來源綁定，再重新讀取核對已管理上傳。
  同一 transaction 保存 Task 與新 Run；舊版取消但原 snapshot、Gate 與核准不變。
  新版沒有輸入核准，必須重新確認才由控制 Worker 檢查，不自動執行 ETL。
- 重複相同 request key／相同補正回同一 child；同 key 不同空白列政策回 409。
- 公開 Run 摘要僅顯示白名單工作表／標頭、政策與指紋，不回傳 upload ID、路徑或樣本。
- 既有「需求與規格 → 補正需求並建立新版」提供 Excel 區塊。
  空白列必須明確選擇跳過或保留 NULL；其餘保護以說明呈現，不要求操作者編寫 JSON。
  保存時鎖住契約欄位與取消操作；摘要支援重新載入與舊版本檢視。

## 驗收

- 真實隔離 PostgreSQL／FastAPI revision 測試：未確認工作表回 422、相同請求冪等、
  不同請求回 409、父版原內容保留、child checksum 更新且無核准。
  未重新核准前 Worker 為 IDLE；核准後通過全檔型別檢查且 `write_started=false`。
- 完整後端：**1587 passed, 95 skipped, 1 warning / 41.61s**。略過不算通過。
- 真實隔離網站：透過上傳／選擇／Task／Run／核准 API 準備合成案例；在隔離 API 容器
  只做一次 control-only Gate，先確認唯一可領取的版本是本案。沒有 AI、Hop 或 Vertica。
  使用者介面選擇政策、保存、重新載入，再從真實 API 核對 parent／child／核准／指紋。
  等待測試僅延後轉送原請求，沒有 fake 成功回應。
- 首次 UI 測試在頁面自動 reload 後取舊 Response body 失敗，但保存已成功。
  修正測試為重新讀取持久化 Run 清單，不刪除該次證據、不放寬產品邏輯。
- 網站完整選跑：**16 passed / 26.3s**，包含 Excel 選擇／補正、專案 CRUD、
  歷史／節點／六頁籤／CSV／雙 CSV 與設定回歸。既有故障模擬及舊產物 fixture
  仍依測試明示，不把整組稱為模型／ETL E2E。390px 無水平溢出，契約欄位截圖已檢視。
- 舊 execution-settings 測試未提供必需 `versions`，產品正確拒絕保存；fixture 已補足
  並新增 `X-Settings-Version` 標頭檢查及現行頁內離開攔截檢查，未弱化設定保護。
- 前端及 API／Web 映像 build 通過；約 513 kB bundle 警告仍保留。
- 兩次唯讀維護檢查通過後更新正式 API／control-worker／web，保留四項 dispatch flags，
  未改 migration／DB volume。正式唯讀指南／集合量測／報告 **3 passed / 18.5s**。
  正式 Run／events／歷史 deliveries 前後皆 **305／2861／24**；ready、execution enabled。
  未呼叫正式模型、未重跑正式 ETL。隔離服務正常停止，合成資料及失敗歷史保留。

## 後續

下一步接通 Excel `execution_preparation`、原生 launcher／參數、runtime／QA 證據，
再以真實模型與 Vertica 驗收完整鏈及可攜 ZIP。SA Excel 專用 prompt 的一致版本化、
既有 Task 換檔／重新選擇、JSON／資料表與範例重建仍需完成。
此次只部署已驗證的契約操作入口，不宣稱正式 Excel 寫入與交付完成。

人工基準維持未量測。第 5 階段及整體目標未完成。
本機 knowledge-workspace 不存在，**尚未持久化至 knowledge-workspace**；
具權限的接續工作須更新 WS-0007，保存此證據連結及上述具体 next action。
