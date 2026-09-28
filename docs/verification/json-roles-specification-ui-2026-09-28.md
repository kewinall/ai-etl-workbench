# JSON 角色交接與規格網站驗證

## 範圍與判定

JSON V5 已接到 SA／Developer 的版本化 context、prompt、結構化輸出、
規格 API 及人工編輯／核准網站。本次不是 JSON 真實模型、Hop／Vertica 或 Release 驗收。
正式 Pilot 未更新；既有 Excel Release 與原 20 案分母未修改。人工基準維持未量測。

## 已實作

- SA JSON context v6、prompt v8，READY_FOR_REVIEW 必須引用 source.0.json_input。
- Developer V5、prompt v8，必須保留已確認來源／結構／政策指紋；拒絕降版、過期 context 與漏引證據。
- 既有 offer／journal／claim 及交接保存使用同一 prompt/context；不新增另一套 Task。
- API 支援 V5 驗證、編譯預覽、保存及版本核准；上游異動使核准失效，歷史保留。
- 網站以可讀欄位呈現 JSON 證據及三個指紋，支援人工規格與核准；不把程式檢查當 AI 審查。
- 候選參數使用 SOURCE_JSON，明列 BOM 副本驗證及 HOP_JSON_INPUT_INCLUDE_NULLS=Y。
- JSON 執行仍以 JSON_EXECUTION_NOT_READY 阻擋，SDM 以 SDM_JSON_NOT_READY 阻擋；網站顯示原因，不提供無效產生按鈕。

## 驗證證據

| 驗證 | 結果 | 邊界 |
|---|---|---|
| 隔離 PostgreSQL 全套後端 | 1850 passed、131 skipped、1 warning，51.99s | 跳過的原生／正式測試不算通過；模型回應為合成 |
| 真實網站／API／PostgreSQL | JSON、Excel 契約、Excel 工作表 3 案通過 | 5195 隔離環境，模型與 ETL 開關全關 |
| 規格歷史瀏覽器 V1／V2／V4 | 3 案通過；與上述合計 6 passed，18.8s | 此 3 案為合成 HTTP 回應，不算資料庫核准驗收 |
| 真實 HTTP 上傳及發行可見性 | 10 passed，1.02s | 不執行 ETL |
| API 與 Web Docker build | 通過 | Web 仍有既有大 bundle 警告 |

JSON 真實網站案例涵蓋：BOM／中文欄位上傳、換檔失效、確認等待鎖定、
欄位式補正、父版本與舊核准保留、Gate CHECKED、來源命名、SA 證據可讀、
V5 規格保存及 reload 後核准有效、JsonInput 編譯候選、SOURCE_JSON 參數、
SDM 未開放提示、390px 無橫向溢位及無頁面例外。最後 Run 為 NEEDS_REVIEW，
write_started=false；CHECKED 是 Gate 結果，不是可交付 Run 狀態。

測試檔：backend/tests/test_json_roles.py、test_json_role_api_integration.py、
frontend/tests/json-confirmation-live.spec.ts。瀏覽器截圖留在忽略的本機 test-results，
未將帶合成執行識別碼的原始畫面或 log 納入 Git。

首次後端測試失敗 2 項，原因是新測試錯查 specification_approval.run_id；
改為 JOIN specification 後全套重跑通過。首次 UI 最後斷言錯將 Gate CHECKED
當 Run state；依 run_queue.complete_gate 修正為 NEEDS_REVIEW 後完整重跑通過。
未放寬程式 validator 或執行／交付門檻。

## 下一步

1. 接通 JSON 執行來源綁定、BOM 副本 lineage、Hop launcher 固定讀取政策與 QA 證據。
2. 接通 JSON SDM／可攜包及独立重播，再以新增合成案例進行真實模型／Hop／Vertica／QA／Release 驗收。
3. 完成受控資料表／範例來源新流程與全站對照；第 5–7 階段仍未完成。

knowledge-workspace 的 WS-0007 遠端仍停留先前階段；本次僅讀取，尚未持久化至
knowledge-workspace。應以本專案證據索引更新其狀態，不複製 source code 或原始資料。
