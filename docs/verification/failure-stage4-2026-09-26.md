# 第 4 階段：失敗診斷與受控修訂

2026-09-26 實作與測試，2026-09-27 補存紀錄。上一輪核准服務額度限制曾阻止文件保存；不影響下列已執行測試，但當時未上版。

## 已接通，尚非真實情境驗收

- 修正 RunQueue.revise 只允許需求補正的限制：已核對結案的 FAILED/HOP_EXECUTION 可建立子 revision。
- 必須保留原 outcome、write marker、輸入與歷史，具備 reconciliation、沒有有效 lease，並使用 ai_sample 不同的新目標；不重跑原 Run。
- 新版不沿用核准／Gate／執行證據，重新確認後從 Gate 開始。
- 唯讀 diagnosis API 核對加密日誌與終態事件 checksum，只輸出固定訊息、行號與指紋，不公開原始 SQL／資料／密碼。
- 網站標示診斷為程式規則而非 AI；診斷不等於已證明根因或回滾，不授予自動修復權限。
- 結案後顯示修訂入口，提示新目標及重新核准。

## 已執行驗證

- 隔離 PostgreSQL 回歸：1031 passed、46 skipped、1 warning，23.30s，exit 0。
- 診斷保密／未知／指紋變更：3 passed，0.15s。
- TypeScript／Vite build 通過。
- 瀏覽器合成 API：核對、衝突、診斷行號、修訂提交、390px 無溢出，2 passed，7.4s。
- API/control-worker/web 與 Worker 映像已重建部署；未呼叫模型、未重跑既有交付。

瀏覽器測試只使用既有 Task 導覽，攔截寫入，不改真實 Run。控制平面測試不等於 Hop／Vertica E2E。

## 下一步與未完成

建立獨立 Task、事前標準答案與新測試目標，經真實 SA／Developer 核准，在受控測試範圍製造缺欄位失敗。
保存 Hop 日誌、目標結構與筆數，核對引擎停止後結案，再建立新目標 revision，重新核准與真實執行／QA。
須證明新結果正確、原失敗仍可追溯，才可宣告第 4 階段通過。目前第 4–7 階段均未完成。
