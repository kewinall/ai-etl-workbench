# 後端合併回歸：2026-09-13

## 本輪實測

- 本機執行 tests，排除 test_api.py，明確關閉 WORKBENCH_ALLOW_DATABASE_TESTS 與 WORKBENCH_NATIVE_HOP_STAGING_TEST：249 passed、52 skipped（4.97 秒）。
- test_api.py 直接使用 app.main 與部署資料庫，未列為無外部依賴單元測試；本次未執行此檔。跳過的 52 項為 opt-in 資料庫／原生 Hop 整合，不補算通過。
- 確認 fixture 的清理範圍與模型合成回應後，暫停 CONTROL worker，在隔離 Compose 執行全部 test_*integration.py：51 passed（7.32 秒）。涵蓋 Run queue、specification API、命名鎖、來源內容／換檔／準備、SA 合成派發、心跳與 migration。
- migration 測試包含重跑不修改設定，以及複製 migration 檔後的 checksum／缺檔拒絕；不修改 repository migration。
- 一項 Starlette TestClient 引用 anyio 舊別名的 DeprecationWarning；未影響測試，目前仍待依賴升級時處理。
- 原 CONTROL worker 已恢復，API ready，execution_enabled=false。

## 證據界線

PostgreSQL 為真正控制資料庫；模型回應為合成。此輪未呼叫 Copilot／Bedrock、未執行 Hop 或 Vertica，不能算四情境、20 案例或 Release E2E。新的 execution_preparation 元件使用最新測試映像驗證，未重建運行中的 API 容器。

回歸未發現新增失敗；下一步仍為完成原子執行授權與 Worker 派發，並在明確的測試連線範圍內驗證 Hop→Vertica→QA→SDM→Release。主管成果報告與完整 UI 任務嚮導也尚未完成。
