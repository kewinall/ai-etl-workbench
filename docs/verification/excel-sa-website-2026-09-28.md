# Excel SA 提示與網站接通（2026-09-28）

## 判定

已部署本輪與前兩輪的 Excel execution／QA／SDM／可攜路徑工程變更，
正式網站健康與唯讀回歸通過。**Excel 真實模型、Vertica 寫入及 Release 全鏈仍待新案例驗收**，
不將提示測試、替身回應或網站健康當作模型／ETL 驗收。

## 變更與實際發現

- SA 新增 Excel 專用提示 v7，指明原生 POI、工作表／標頭與全部讀取政策、三重指紋，
  區分來源確認與執行證據。CSV 提示原文及 v6 保持不變。
- gateway、授權 offer、journal 與 Worker claim 共用同一 material；claim 再檢查
  prompt／schema 原文與指紋／版本，部署版本不符時停於 `STALE_NOT_DISPATCHED`，不偷偷重送。
- 本機 SA bridge 傳回持久化 prompt version；Windows Worker trace 保留該版本。
  既有單次模型、無工具、無自動重試、lease 保護維持不變。
- 實際檢查發現網站 SDM 預覽只接受 V1–V3，會拒絕新的 V4 文件；現已加入
  Excel 讀取契約與指紋顯示及格式檢查，缺少／錯誤政策仍拒絕顯示。
- 編譯預覽的 Excel 參數說明由錯誤的 `SOURCE_CSV` 改為 `SOURCE_XLSX`。

## 證據

| 檢查 | 實測結果 |
|---|---|
| SA gateway／Excel prompt | 11 passed；使用明示 synthetic completion，不是真實模型 |
| 完整隔離後端 PostgreSQL | 最終 1680 passed、105 skipped、1 warning，36.65 秒，exit 0 |
| Excel journal | 真實 PG 保存 v7 與 offer 相同指紋；原子 claim 一次；模擬新版部署後舊提示拒絕取件；未呼叫 provider |
| CSV 固定 commit 相容性／source distribution／本機 Worker | 14 passed |
| 隔離 Playwright | 8 passed / 16.7 秒：真實 Excel 上傳／補正 2 項、SDM 顯示 guard 3 項、合成 API 的規格 V1／V2／V4 操作 3 項 |
| 既有功能隔離回歸 | 4 passed、2 skipped / 8.6 秒；專案與 Task 導覽、設定、六頁籤，略過項目不算通過 |
| 前端與 API／Web 映像 | build 通過；約 514.58 kB bundle 警告仍存在 |
| 正式唯讀指南／集合／報告 | 3 passed / 15.8 秒，不發出寫入請求 |
| 正式資料保全 | 部署前後 Run／event／delivery 均 305／2861／24；ready、execution enabled |

V4 規格頁 390px 無水平溢出，保留核准、編輯新版與取消操作；截圖已檢視。
合成 API 的 SDM 預覽不能代替真實 SDM 保存、下載或 Release 的資料庫驗收。
隔離環境正常停止、volume 及合成歷史保留；未修改正式 migration、資料卷或既有交付。
正式更新前兩次只讀維護檢查通過，但這不是持續 admission lock，仍依單一操作者協調。
四項既有執行／角色派發 flags 保留，沒有擴大自動執行權限。

## 下一步與限制

1. 建立全新的合成 Excel 案例，明確工作表、標頭、空白列、型別、Filter／Aggregation 與固定標準答案。
2. 依平台正常版本化流程做真實 SA→Developer→編譯→Hop→Vertica→QA，保留所有失敗／修訂證據，
   不以手寫 agent 結果或直接 DB 修改繞過角色來源檢查。
3. 核對網站節點、執行及 QA；產生 SDM，於獨立 Vertica 目的環境重播 HWF，
   確認可攜 ZIP 不含來源資料／機密，再依已授權的 Pilot 核准範圍正式 Release。
4. JSON／資料表來源、受控範例重建、全站功能對照及階段 6–7 其餘事項仍未完成。

人工基準維持「未量測」，不計算改善率。已唯讀重查 knowledge-workspace WS-0007，
其進度仍落後，既有寫入限制不繞過；**本次尚未持久化至 knowledge-workspace**。
具允許寫入權限的接續工作須同步最新 project commit、本證據連結與上述具體下一步，
保留其他專案及歷史，不公開執行識別碼或原始資料。
