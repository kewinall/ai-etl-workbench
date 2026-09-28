# JSON 來源確認、需求補正與網站驗證（2026-09-28）

## 判定與範圍

已接通 managed JSON 來源確認、Requirement Gate、Run revision、欄位式網站確認及歷史回讀。
**本次僅部署隔離 5195 測試環境，未部署正式 Pilot；尚未完成 JSON 模型／Hop／Vertica／
QA／SDM／Release 全鏈。第 5–7 階段與整體目標保持未完成。**

原 Excel 正式交付與原 20 案不重跑、不改分母。人工基準依操作者決定維持未量測，
不得以代理工時或推估值填入改善率。

## 已實作

- `POST /api/task-sources/{upload_id}/json-profile` 僅接收 UUID 對應的 managed upload、
  checksum 與 byte count；不接受任意檔案路徑。完整重新解析後綁定 root shape、欄位、
  筆數、profile version、profile checksum；確認範圍明確為 `INPUT_PROFILE_ONLY`。
- 新 Task 的實際 JSON 來源須通過確認；網站支援正常 STAGE 上傳 JSON，換檔後清除
  舊確認，確認請求進行中不能建立或取消整份草稿。只保存結構 metadata，不保存預覽資料列。
- Gate 使用一次驗證後的 byte snapshot，不重開原始檔；JSON 讀取契約綁定確認內容。
  少契約為 MISSING、版本或互斥契約不符為 CONFLICT，不產生 ETL 執行權限。
- 修訂綁定同一 Run input checksum，建立子版本並要求重新核准；舊 input snapshot、
  舊核准與歷史不變。重複相同請求回傳同一新版，不同 payload 重用 key 回傳衝突。
- Run API 僅呈現政策與安全指紋／結構摘要，不把上傳 ID、樣本或實際路徑放入 input summary。
- 網站以明確欄位說明 UTF-8／BOM、缺值、空字串、巢狀／額外／重複欄位、全 NULL 列
  及停止政策；勾選後才提交契約。舊版沒有確認證據的 JSON 歷史仍可查看，明示需重新
  建立已確認來源的 Task；本輪未提供舊 JSON 原地換檔。

## 驗證證據

| 驗證 | 結果 | 不代表 |
|---|---|---|
| JSON profile／binding 單元測試 | 13 passed，1.00 秒 | 不代表真實 ETL |
| 完整隔離 PostgreSQL 後端回歸 | 1771 passed、123 skipped、1 warning，48.77 秒，exit 0 | skipped 不計為通過 |
| 真實瀏覽器 JSON + Excel 上傳／契約回歸 | 3 passed，9.7 秒 | 無模型、無 Hop、無 Vertica 寫入 |
| 隔離真實 HTTP upload + 來源發行可見性 | 10 passed，1.00 秒 | 不代表正式 Pilot 已部署 |
| 前端 TypeScript／Vite 及 API／Web Docker build | 通過 | 仍有既有 bundle 大於 500 kB 警告 |

後端新增 `test_json_revision_integration.py` 使用真實隔離 PostgreSQL：初版 NEEDS_INPUT，
錯誤 root shape 被拒、新版 idempotency／舊版保留／新核准、Gate CHECKED 與 BOM 雙指紋
均驗證。JSON proof 的 `type_conversion_verified`、`execution_authorized` 仍為 false。

瀏覽器 `json-confirmation-live.spec.ts` 使用真實 API 與 DB，不 mock 回應：完成中文欄位／
BOM／缺值來源上傳、未確認禁止建立、換檔清除確認、請求等待鎖定、建立 Task、未確認 API
反例、控制 Worker NEEDS_INPUT、勾選政策補正、重載與前後版本／核准回讀。
390 px 無水平溢出、無 pageerror；已檢視來源確認及欄位式政策截圖。
Excel 的來源選擇及契約補正兩項舊測試同批重跑通過。

初次 JSON 瀏覽器測試在保存成功後遇到頁面自動重載，使測試端 response body 消失。
改為從 API 回讀已持久化的新版本後，整批三項重新通過；不是放寬保存或歷史斷言。

測試環境模型與 ETL 派發均停用、無 Control Worker 背景輪詢，只針對確認的合成 Run
執行一次控制檢查；沒有連接真實模型或業務 DB。既有正式服務不重建。

## 下一步

1. JSON 全檔 typed validation、版本化 Specification 與 Naming 一致性；型別不符不能進寫入。
2. 將原始／reader 雙指紋、JSON null 語意與來源節點清單接入 reservation、launcher、
   QA、SDM、manifest 及可攜重播，保留 CSV／Excel 既有版本相容性。
3. 新獨立案例完成真實角色到 Release 全鏈與正式網站回歸，再判定此來源流程完成。

本輪只讀取得 knowledge-workspace WS-0007，仍為 2026-09-26 的舊進度；
**尚未持久化至 knowledge-workspace**。接手者需以本檔及 staged-completion.md 同步
工程證據、人工基準未量測及剩餘事項，不複製上傳資料、憑證或私有 runtime 身份。
