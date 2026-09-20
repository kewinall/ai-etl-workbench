# SDM 規格內容候選

舊 release.create_sdm 只將整份 Naming Contract 列為欄位對照，缺少實際輸出投影及聚合來源。新增 sdm_specification.build_sdm_candidate，先重用 validate_specification，再依 output_columns 順序建立 mappings，使用同一份 output_types 與命名參照；DIRECT、GROUP_KEY、SUM、COUNT_ROWS 等操作及來源原名／stream name 可追溯。

保留 filters、filter/null policies、aggregation、target 及命名／規格 checksum；不複製連線設定、任意命名理由或來源檔案路徑。這不取代最終敏感內容與 portability 掃描。

輸出為內部結構化 SDM_CANDIDATE_NOT_RELEASED，qa_passed/release_ready=false。尚未保存成 Excel、掛載 API 或部署；未修改舊 SDM 檔案或啟用舊 release 入口。

## 驗證

後續已部署：GET /api/tasks/{task_id}/runs/{run_id}/specifications/{specification_id}/sdm-preview，僅使用當前已核准規格及命名，網站規格頁提供表格預覽。仍無 Excel 或 Release 下載。隔離 PG／候選測試 7 passed（0.96 秒），包含未核准／過期／跨 Task 拒絕及不新增事件；前端建置通過；部署後真實 UI/API/PG 與六頁籤回歸 2 passed（13.3 秒）。案例 TASK-20260913-0208、Run 563e6614-6259-4494-8ffc-4f27134b5629、規格 b02c63fa-c2fe-4a4c-a00a-e53a66f0d6f4。實測來源「金額 → amount」、total_amount、COUNT_ROWS 對照及 390px 無溢出。API／CONTROL／web 已更新；無模型或 Vertica 呼叫。

- SDM、ETL specification、HPL compiler 合併 52 passed，0.20 秒。
- 驗證投影順序、聚合 lineage、COUNT_ROWS 不偽造來源欄位、直接對應、checksum 確定性、輸入不變及無效／草稿命名拒絕。
- 初次無聚合測試因保留多餘 metric 命名而失敗；修正 fixture 的命名契約，沒有放寬生產驗證。

仍需接到保存且核准的 spec／QA 證據、Excel 渲染、manifest 一致性及 Release gate；不能將本次純函式測試計入真實 Hop／Vertica／SDM／Release E2E。
