# JSON QA 證據與來源格式呈現（2026-09-28）

## 判定

本階段工程與隔離回歸通過，未部署正式 Pilot；不宣告 JSON 真實 E2E 或第 5–7 階段完成。
人工基準依操作者決定保留未量測，不估算工時改善率。

## 修改與原因

- JSON 規格 V5 使用 QA context 15、prompt 12。原始來源、BOM 讀取副本、契約、完整型別檢查、規格與 HPL 指紋相互核對。
- 獨立檢查 RowGenerator → JsonInput → SelectValues 三節點選項及連線，不以重算 XML checksum 掩蓋語意變更。
- QA 必須取得實際保存 log 的唯一 JSON launcher receipt，並綁定 log checksum。receipt 不是 QA PASS 或 Vertica 結果證據。
- 修正通用節點驗證器將已受控 JSON 來源誤判為未知／待複核的問題：只在完整 V5 編譯與 XML 契約一致時允許指定兩個來源節點；額外 RowGenerator／腳本仍拒絕，沒有全域放寬清單。
- 修正 QA 歷史畫面無條件讀取 CSV 契約的錯誤。單 CSV、多 CSV Join、Excel、JSON 各呈現對應來源；未知格式明確提示缺少資料。
- 需求條件使用原始 JSON 欄位名稱核對；GT 被改成 GE 等語意差異仍被攔截。

## 可重現驗證

| 驗證 | 結果與範圍 |
|---|---|
| 隔離 PostgreSQL 全後端 | 1962 passed、135 skipped、1 warning，54.13 秒；跳過項目不算通過 |
| 本機針對性回歸 | 116 passed，含 JSON／Excel QA、選項、節點政策及發行檔案可見性 |
| 瀏覽器 | 6 passed，11.8 秒；1 項真實隔離 JSON 上傳／補正／核准流程、5 項合成 QA 歷史格式呈現 |
| 窄版面 | 上述 QA 格式在 390px 無橫向溢位、無頁面 JavaScript 錯誤；JSON／Excel／Join 截圖已人工檢視 |
| Build | API 與網站 Docker build 通過；網站保留既有大 chunk 警告 |

後端命令：`docker compose -p ai-etl-locked-regression -f deploy/compose.p0-tests.yml up --no-build --abort-on-container-exit --exit-code-from tests`。

網站命令（frontend 目錄，WORKBENCH_TEST_URL 指向隔離 5195）：
`npx playwright test tests/qa-source-formats.spec.ts tests/json-confirmation-live.spec.ts --reporter=line`。

新增測試：`test_json_runtime_options.py`、`test_json_qa_context.py`、`test_json_qa_integration.py`。
涵蓋選項篡改、重複欄位／節點、型別與指紋不符、缺 receipt、重複領取、合成模型建議不得推翻程式失敗及歷史保存。
PG 整合測試的 Hop log、答案與模型回覆皆為明示合成資料，沒有真實 provider 或 Vertica 呼叫。
缺少查詢來源證據時結果保持 MISSING／NEEDS_REVIEW，不會取得 Release 核准。

## 下一步與保留項目

1. 接 JSON SDM、可攜 HWF／ZIP 與獨立重播證明，再做新案例真實角色／Hop／Vertica／QA／交付驗收。
2. 正式部署須同時重建 API 與 Worker，避免舊 Worker 缺少 JSON launcher receipt；本輪未替換正式容器或重跑既有 ETL。
3. 第 5 階段其餘來源與全站功能對照、第 6 階段列印／量測、第 7 階段可靠性剩餘工作仍保留。
4. 協調狀態尚未持久化至 knowledge-workspace；本專案索引與本文件保存本階段證據與下一步。
