# Task 六頁籤工作區驗證

本批範圍為 P1 網站重整及既有能力保存，不是 Hop／Vertica 全流程完成。

## 原功能對照

| 原畫面 | 新位置與保留內容 |
|---|---|
| Pilot 執行準備 | 概覽：設定阻擋、最新 Run 與下一步；不把設定完整當連線成功 |
| 準備版本 | 需求與規格：建立、確認／拒絕、取消、補正、新舊版本、SA 引用與用量 |
| 第一層 Task 設定 | 需求與規格：完整來源、目標、欄位與錯誤情境設定 |
| 第二／三層節點 | 產物與流程：所有節點可點、輸入輸出與相關事件 |
| 第四層 Hop／SQL | 產物與流程：transforms、hops、XML 及 SQL |
| 第二層執行紀錄 | 執行與 QA：進度、筆數、錯誤結果、事件與 Hop Log |
| 第五層成功成果 | 交付：原成功產物下載，明示不是新版 RELEASE_READY |
| 控制紀錄 | 協作紀錄：選擇 Run、人工輸入決定、控制事件、SA 保存狀態 |

各頁籤為 `/projects/{project}/tasks/{task}/{tab}`，舊 Task URL 仍有效並開啟概覽。需求補正表單在切換頁籤後保持掛載，不會丟失草稿。瀏覽器重載或離開 Task 的保護尚未加入。

## 本批證據

- TypeScript／Vite 與隔離 Docker 網站建置通過；API、Worker、資料庫結構及執行開關未變更。
- 網站回歸 7 passed；付費模型與 native lifecycle 兩個 opt-in 測試明確跳過。
- 真實網站／API／PostgreSQL：專案 CRUD、設定保存重載、歷史 Task、版本確認、控制 Gate、補正、授權排隊／取消及拒絕等既有回歸仍通過。測試模型路由為合成 Bedrock，對應 SA worker 未啟動，不呼叫模型。
- 六頁籤測試：390／768／1440px、鍵盤左右鍵、深連結重載、瀏覽器返回、節點詳細資訊、XML、SQL、Log 及下載內容核對。
- 隔離資料庫沒有成功歷史 Task，因此 Hop 產物與下載使用 **browser-only 合成回應** 驗證 UI 契約，最後核對資料庫 Task 仍為 CREATED。不是實際引擎產物或交付證據。
- 唯讀查閱既有真實 SA：Task `TASK-20260913-0018`，Run `0e02d635-3f87-42ff-acd9-1cb19856dfd2`，協作頁能顯示 `copilot/gpt-5.4`／`VALIDATED_NOT_APPROVED`；需求頁保留 NEEDS_INPUT、兩個問題、1,685 輸出 Token。未再呼叫模型。
- 畫面證據：`outputs/pilot-evidence/task-workspace-20260913/real-sa-collaboration.png`。瀏覽器測試截圖位於 `frontend/test-results/`，屬驗收暫存而非 Release 產物。

## 仍不完整

Developer／QA 角色交接、命名／規格／設計版本差異、標準答案執行、SDM／manifest／人工 Release 核准尚未接通。六頁籤只呈現已存在的能力；未放置可點卻無功能的新交付按鈕。

舊五層元件保留在 main.tsx，主 Task 路由不再使用。清理舊元件仍需涵蓋其他使用點後才能刪除。P0–P3 整體目標保持未完成。
