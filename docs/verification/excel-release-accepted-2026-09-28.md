# Excel 真實交付驗收（2026-09-28）

## 判定與範圍

新增合成 Excel 案例已完成真實 SA／Developer／QA、原生 Hop、Vertica 固定答案、
SDM、獨立環境 HWF 重播、網站核准及正式 ZIP 下載。不是 mock E2E。
**第 5–7 階段仍未完成**；JSON、資料表／受控範例來源及完整網站對照另行驗收。
原凍結集合保持 20／20 可交付、19／20 原情境匹配，不把此新增案例併入分母。
人工基準依操作者指示保留未量測，沒有代理工時或改善率。

## 部署及歷史保護

- 執行版本：`caf92f4bbe244bf803d11508bb7264da2033f9d7`。重新建置最終 API／Worker，
  migration 057 additive 升級；維持原執行與三角色派發開關。
- 部署前控制 DB 備份 1,402,881 bytes，SHA-256
  `6478b888ad0d44006c4f14735460f23276ad89a96c4bd278e3859220e60262e8`。
  已檢查 archive list，不代表這份新備份已做還原演練；備份不入 Git。
- 正常網站核准「只重新比對」，scoped Worker 讀取已寫入的目標並保存 MATCH／來源證據。
  原後處理失敗與 NEEDS_REVIEW 派發沒有改成成功；沒有重跑原 Hop。
- 最終同 Run 的 WRITE_STARTED、HOP_EXECUTED_QA_REQUIRED、COMPARISON_RECOVERY_COMPLETED
  各 1 筆。控制資料由 307 Run／2896 event／24 delivery 變為 307／2910／25。
  原 Windows DB、歷史產物及原 20 案不覆寫、不刪除。

## 真實案例證據

| 項目 | 結果 |
|---|---|
| Excel 規則 | 明細工作表、標題列 2、略過全空列、缺格 NULL、拒絕公式／非空額外欄、文字不 trim |
| 型別及轉換 | 金額 NUMERIC(18,4)，amount > 100，依 category 分組，SUM → NUMERIC(24,4)，COUNT_ROWS → BIGINT |
| 固定答案 | 2／2 MATCH：A＝150.25／1，B＝500.50／2；missing／unexpected 都為 0 |
| 來源證據 | 已保存 BOUND_PLATFORM_TARGET，與原核准、一次写入、原查詢及日誌指紋綁定 |
| 真實 QA | Copilot gpt-5.4，PASS、無 issue；28,594ms、1 session、0 retry、0 tool operation |
| 用量 | CLI 回報 6.2224 AI credits、1 premium request；PARTIAL，Token 未回報，非貨幣成本 |
| QA／SDM | 正常 API 核准當前 binding，產生並保存候選 SDM，不改写舊版本 |
| 可攜驗收 | 獨立 Vertica 的新目標，原候選 HWF／HPL／DDL 與受控 XLSX 重播 PASS；沒有重播原目標 |
| 真實網站 | 7 個節點均有完整計數且 errors＝0；SDM 歷史可查看，核准勾選保護、重載與正式下载通過 |

本案例包含首版精度補正及已保存的後處理失敗，不能呈現為首次全鏈通過。
QA 的合成行為參考不取代真實 runtime 證據；不擴大為所有 Excel 型別、工作表或整批 rollback 保證。

## ZIP 與閱讀性

正式 ZIP 為 11,208 bytes，SHA-256：
`603b9e974338cfe9cd25b13d1a7ef680b7b12bd96ff2ba63992ddcb46eef1c2a`。

- 實際網站下載及再次唯讀下載指紋一致，ZIP CRC 通過。
- 僅含 `hop/pipeline.hpl`、`hop/workflow.hwf`、`vertica-ddl.sql`、`SDM.xlsx`、
  `parameters.example`、`release-manifest.json`；不含來源資料、控制 DB 或私有 log。
- manifest 的 5 份產物大小／SHA-256 全數吻合；核准及規格 binding 一致，
  `RELEASE_READY`／`qa_passed`／`ISOLATED_HOP_RESULT_VERIFIED` 來自已保存流程。
- 正常核准／下載執行既有內容 gate；另以實際交付 SDM 唯讀匯入、渲染查看兩頁籤：
  欄位對照、來源規則、型別、Naming／Specification／QA／可攜指紋均可閱讀。
  沒有重新匯出或修改已核准 SDM；此為 renderer 視覺檢查，不是原生 Microsoft Excel 操作測試。

## 可重現網站回歸

新增 opt-in `comparison-recovery-live.spec.ts`、`excel-release-live.spec.ts`，
從環境傳入既有合成 Task／Run／Project，不在程式碼保存本機身份。
需要第一次變更时須另有明確 consent；已完成版本重跑只讀、不重新呼叫模型／Hop。

正式唯讀回歸 5 passed（21.4 秒）：上述兩項、操作指南、量測及主管報告；
包含 390px 版面、頁面錯誤、原寫入數、下載 SHA 與既有案例分母。
前次實際確認恢復 1 passed（1.9 秒），實際 Release 核准 1 passed（3.0 秒）。
既有 1702 項後端回歸為此部署版本的前次證據；本輪未把它冒充再次執行。

## 接續與限制

1. 完成 JSON 來源的 immutable 讀取契約、型別／命名、版本化 specification、Hop 編譯、
   QA／SDM／可攜 Release，再用全新合成案例做真實驗收。
2. 接續資料表／受控範例表新版流程及網站完整功能清單；不可刪非平台管理或跨 Project 表。
3. 報告列印分頁、完整 dispatcher 失聯、宿主機啟動／長時穩定、備份保管及還原權限仍待驗收。
4. knowledge-workspace WS-0007 仍待同步：**尚未持久化至 knowledge-workspace**。
   接手者應保存本證據連結、project 最新 commit、未量測人工基準與上述下一步；不複製來源資料或密鑰。
