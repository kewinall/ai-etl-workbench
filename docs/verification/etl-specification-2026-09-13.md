# EtlSpecificationV1 與編譯預覽驗證

## 範圍與原因

舊 `execution.py` 的 CSV 與聚合產生器存在固定「前 10 筆」及固定計算轉換，不能直接當成新版明確規格的編譯器。本批保留舊歷史路徑，新增版本化規格驗證與編譯計畫。**沒有產生 HPL、執行 Hop 或寫入 Vertica。**

## 契約與接點

- `backend/app/etl_specification.py`：嚴格結構化 `EtlSpecificationV1`，不接受任意 SQL、Join／row_limit 等額外欄位。固定支援子集為單一 CSV、ALL（AND）Filter、可選分組聚合、投影及 APPEND。
- Filter 明確指定欄位、運算子、型別化常數及 EXCLUDE_UNKNOWN；decimal 使用精確字串，boolean 不接受字串或數字冒充。IS_NULL／IS_NOT_NULL 必須不帶常數。
- 聚合支援 SUM、COUNT_ROWS、COUNT_NON_NULL、MIN、MAX；輸出名稱須已包含於同一 NamingContract，衍生欄位來源鍵為 `$metric.<id>`。SUM／COUNT 及來源解析型別均檢查相容性；不把精度縮減視為可接受。
- Run、input/settings checksum、命名 ID／version／checksum 必須一致；輸入已確認、目前未寫入、Gate 通過才可完成結構驗證。這仍不是 SA 語意或人工規格核准。
- `POST /api/tasks/{task_id}/runs/{run_id}/specification/validate` 接受 EtlSpecificationV1 本體。伺服器從既有資料表讀取 Run、核准與最新命名契約；不接受呼叫端自行宣稱命名已確認。較新的 DRAFT 存在時不回退舊 CONFIRMED。
- 有效回覆含 `VALIDATED_NOT_APPROVED`、specification_checksum、plan_checksum、source-to-stream 映射、明確 Filter、SortRows→GroupBy 與輸出投影。`compiler_status=PLAN_ONLY_HPL_NOT_GENERATED`、`execution_authorized=false`。
- API 不保存候選規格、不建立產物、不派發工作、不修改 Run；目前尚未提供網站規格編輯／確認面板。

## 測試證據

| 項目 | 結果 |
|---|---|
| 選定本機完整回歸 | 196 passed，4.98 秒；包含最後補上的 BIGINT→INTEGER 縮減拒絕測試 |
| 隔離 PostgreSQL／API | 34 passed，4.79 秒；其中 2 項新增規格預覽驗收 |
| 規格計畫 | CSVInput→FilterRows→SortRows→GroupBy→SelectValues→TableOutput；原始欄位順序、中文到英文映射與明確條件保留；不添加 10 筆上限或固定 Calculator |
| 反例 | 任意 SQL、未知欄位、過期 checksum、草稿／跨 Task 命名、聚合名稱碰撞、型別不符、精度縮減、未支援写入與日期範圍均阻擋 |
| 無副作用 | 預覽前後 Run 完全相同；specification、hop_artifact、agent_invocation 對該測試 Task 的筆數仍為 0 |
| 實際部署 | API 容器 OpenAPI 確認新路由存在；由網站送不完整規格收到 HTTP 422。網站根 `/openapi.json` 不代理 API，不以該靜態頁當 API 證據 |
| 網站 | 修正表單競態及 nginx 後最終 8 passed，19.9 秒；真實模型與 native lifecycle 2 項 opt-in 案例跳過 |

模型派發仍關閉，本批没有新的 Copilot 呼叫；資料庫仍只有先前 1 筆，待派發 0 筆。測試提供的規格與命名契約是合成 fixture，不是模型或真人正式核准的案例成果。

## 同輪回歸缺陷與修正

第一次網站回歸發現：使用者選擇「沿用平台 AI」後，PUT 送出的 AI 預設已被改回 nova-default，資料連線仍為空字串。問題在 API 儲存前：新增專案後的延遲 GET 更新 selected 物件，觸發 restore(selected)，覆蓋編輯中的選擇。

ProjectWorkspace 改為依 projectId 完成載入與表單初始化後才開放編輯，不再因 selected 物件更新自動重設草稿。新增測試刻意暫停新增後的 GET，確認不會開放尚未初始化的表單，再核對 PUT、資料庫與重載後均保留空字串繼承值。

### API 重建後 nginx 502

最後部署檢查發現 API healthy，但 nginx error log 仍連向重建前地址；docker inspect 顯示 API 已換址。原設定在 nginx 啟動時固定解析 api 名稱。

`deploy/nginx.conf` 改為 Docker DNS resolver（5 秒快取）與變數形式 proxy_pass，保留原 URI 及固定 api 服務目標。nginx 原生 `-t` 成功，網站 API ready 恢復，全部 8 項網站操作回歸通過。

另外實測只重建 API／control-worker，網站 container ID 不變，API ready 仍成功；但此輪重建取得相同 IP，不能把它當成已證明不同 IP 的 DNS 快取更新。刻意换址演練仍待完成。

## 尚待完成

規格持久化／差異與人工核准、SA→Developer 交接、原生 HPL／HWF／DDL 編譯與 Hop metadata 驗證、實際檔案解析一致性、Vertica 標準答案 QA、SDM／Release，均未因本批而完成。Join、REPLACE／UPSERT、日期範圍編譯等需後續擴充，不得靜默降級。P2 四案例與 P3 20 案例／人工基準仍未驗收。
