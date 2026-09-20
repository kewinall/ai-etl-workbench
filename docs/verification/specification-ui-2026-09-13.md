# Task 規格歷史與核准 UI

已部署在 Task → 需求與規格 → 執行準備版本 → ETL 規格版本。使用者可載入已保存規格、選版本、查看目標／篩選／分組／聚合／輸出順序、檢查 Hop 編譯候選，並勾選明確確認後核准。HPL 置於可展開技術細節，主內容不是 JSON 編輯框。

後端 history 新增 `reviewable`，根據最新規格、Run、NamingContract 與輸入／設定計算；UI 不自行決定核准資格，POST 仍再次驗證。歷史核准失效時保留紀錄並停用核准與編譯按鈕。核准成功文案明示沒有啟動 Hop／Release。

## 2026-09-13 驗證

- TypeScript／Vite 建置成功，API／web 已部署，CONTROL Worker 已恢復，模型派發維持關閉。
- 全站瀏覽器 9 passed（23.5 秒）、2 opt-in skipped。涵蓋新頁確認 checkbox、checksum request、核准成功、編譯候選展開、失效後停用及 390px 無水平溢出。
- 新規格 UI 測試使用瀏覽器合成 Run／規格回應，沒有寫入假的核准或 Hop 成功資料。因此它證明互動契約，不是 UI→真實規格核准 DB E2E。
- 另 6 項真實 PostgreSQL API 測試再次通過，新增 assert 驗證最新未核准規格 reviewable=true、舊版與上游變更後 reviewable=false。
- 窄版 screenshot 已檢視；長 checksum 與 HPL 可換行，元件按鈕無水平溢出。整頁截圖應在 scrollTop=0 取得，避免 sticky 導覽出现在合成長截圖中段。

## 剩餘範圍

規格建立／編輯表單尚未完成；沒有已保存規格時只顯示具體原因，不假造規格。新 UI 亦尚未完成真實 DB 的完整點選核准驗收。協作時間線、Worker 下游查核、不可變來源、Vertica QA、HWF／DDL／SDM／Release 仍待接通。P0–P3 未完整達標。
