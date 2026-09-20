# 真實規格 UI → API → PostgreSQL → 時間線驗收

2026-09-13 完成不攔截 API 回應的規格控制流程：正式 API 建立合成 Project／Task／NamingContract；網站建立準備版本、確認輸入；CONTROL Worker 真實檢查；網站手動選擇 Filter／GroupBy／SUM／COUNT_ROWS／輸出順序；保存、核准、重載確認、編譯預覽；協作時間線回讀。

## 發現並修復的既有問題

第一次命名確認回傳 500。API 接受任意 dict，但 repository 必須使用 confidence／reason，缺欄位時發生 KeyError。已新增 NamingColumnInput／NamingContractInput 驗證，必填欄位缺漏現在回 422；confidence 限定 0–1 且有限值，不捏造預設信心度。6 項單元測試及真實 API 缺欄位 422 回歸通過。

## 證據

首次通過案例：

- Task `TASK-20260913-0082`
- Run `c50cb516-4a19-4aae-ad6c-2271ce012bb5`
- Specification `eb99a2e8-84cd-47cd-826a-4e2834439a98`
- Approval `0a8c9bf3-d67a-437f-ab2b-fa200696c14c`
- 規格 checksum `364354537c504fb6c096249125a50278e1b0be4e5cf523cb470d466e6f4a2f59`

直接 PostgreSQL 查詢確認 1 筆規格、1 筆核准；事件順序包含 SPECIFICATION_SAVED／SPECIFICATION_APPROVED；model_calls=0、hop_artifacts=0、write_started=false。

加入命名缺欄位回歸後全站再次通過：10 passed（26.1 秒）、2 opt-in skipped。第二次真實案例 Task `TASK-20260913-0087`、Run `ddda9995-e922-4a34-8964-af7abb5552d3`、Specification `c0d2283a-b2bd-4f62-a923-e88f84da62be`。其證據 JSON 與時間線 PNG 由 Playwright 寫入 `frontend/test-results/specification-live-*/`，已目視核對真實時間線內容。

此案例沒有 page.route/mock，核准有效與重載保存由正式 API／網站確認；同一份程式生成 HPL 預覽，但沒有執行 HPL。

## 測試環境與回復

只用合成需求與欄位。為讓規格前置設定成立，暫用明確命名的 synthetic AI profile 與 synthetic-no-connection 連線 metadata，沒有測試或使用該連線。結束後恢復原資料連線設定，取消測試 Run，保留 Project／Task／規格／核准與事件。

因此現在該 Run 為 CANCELLED，核准歷史可查但不再是有效執行授權。不可將保存於測試當下的 approval_effective=true 與回復後現況混淆。

## 重現

frontend 目錄設定 `WORKBENCH_TEST_CONTROL_WORKER=1` 後執行：

```powershell
node node_modules/@playwright/test/cli.js test specification-live.spec.ts --reporter=line
```

需隔離 Pilot ready、execution_enabled=false 及 CONTROL Worker。測試會暫時修改 Pilot 連線 metadata，結束恢復，不應在多人共用環境並行操作。

## 不包含

NamingContract 尚由測試用正式 API 準備，沒有把命名表單 UI 納入本案例；SA／Developer／QA 真實協作、模型呼叫、來源 bytes 綁定、Hop→Vertica→QA→SDM→Release 均未驗收。只補齊規格控制流程，不代表 P1 或 P0–P3 全部完成。
