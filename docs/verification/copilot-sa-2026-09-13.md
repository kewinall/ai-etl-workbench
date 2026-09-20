# 本機 Copilot：單次真實 SA 驗收

## 結論與範圍

2026-09-13，使用者明確同意改用目前登入的 Copilot 額度，做一次真實驗收，不自動重試。本次已完成網站 → 授權 API → PostgreSQL 排隊 → Windows Worker → Copilot CLI → 結構驗證 → PostgreSQL → 網站回讀。

**通過的是模型介接與紀錄流程，不是需求合格、ETL 成功或 Release 完成。** SA 實際回覆 `NEEDS_INPUT`，指出 CSV 輸入格式契約及額外欄位處理規則未明確。

| 證據 | 實測結果 |
|---|---|
| 本機 CLI | GitHub Copilot CLI 1.0.80（執行版本） |
| Provider／模型 | LOCAL_COPILOT／copilot/gpt-5.4 |
| Task | TASK-20260913-0018 |
| Project | bdd515cf-0a77-4305-acc0-931dbcdc9c4e |
| Run | 0e02d635-3f87-42ff-acd9-1cb19856dfd2 |
| 呼叫編號 | 96ab57ae-0640-47c3-af94-3f5ca3ff8e86 |
| Context checksum | 07c8a2bbf1e380fbd9b8041610d3b99bc47cae9f020b2d4d8647bb203cd03c5a |
| 呼叫紀錄 | PostgreSQL 查詢確認一筆；VALIDATED_NOT_APPROVED |
| SA 業務判斷 | NEEDS_INPUT，2 個需求問題 |
| CLI 執行耗時 | 18,969 ms，包含 CLI 啟動與模型處理，非純供應商延遲 |
| 輸出 Token | CLI 回報 1,685 |
| 輸入／總 Token、AI credits | 未回報，記為不可用，不補零、不估算 |
| Premium requests | CLI 回報 0；不代表已證明零成本 |
| CLI sessions／自動重試／工具執行 | 1／0／0 |
| Hop／Vertica／Release | 未執行；write_started=false |

## 安全與部署邊界

- 不擷取或複製 GitHub 登入 Token。Windows Worker 使用使用者既有 CLI 登入。
- 不新增 HTTP 監聽或開放 PostgreSQL port。Worker 透過固定 Docker exec bridge 存取同一份控制資料；此方式需要本機既有 WSL/Docker 操作權限。
- Prompt 經 literal argv 傳入，不經 cmd.exe 插值。CLI 在暫存空目錄執行，禁用可見工具、內建與已設定的 MCP、custom instructions、remote export 與自動更新。
- Copilot 的單次政策與 Bedrock 政策分開：Copilot 最多一個 CLI session，不自動重試；不宣稱 CLI 支援 2,048 輸出 Token 硬上限。
- 輸入、設定、Context、prompt/schema checksum 與 Operator 綁定授權。租約失效不可回寫成功或重送；尚未領取可以取消。
- Docker SA Worker 只領取 Bedrock/Proxy；Windows Worker 只領取指定的 LOCAL_COPILOT 版本。

## 測試資料與回復

本案來源為合成欄位與需求文字。為驗證 SA 設定快照，測試期間暫存一組明確標為 SA-only 的假連線 metadata，**從未測試或連接 Vertica**。結束後恢復原平台連線設定，取消此測試 Run，保留 Project、Task、授權、trace、SA 結果與事件。

因此現在畫面會提示此歷史版本不符合目前設定；不得沿用該核准直接執行。這是刻意保留的版本保護，不是可交付的 ETL 案例。

本機截圖保留於 `outputs/pilot-evidence/copilot-0e02d635/`：`copilot-real-sa.png`、`sa-panel.png`。不將這些 runtime 證據當作已核准 Release artifact。

同目錄 `post-test-api-evidence.json` 為測試完成並恢復設定後的 API 回讀，SHA-256：`B2D4D9BBBB9560DDFCB649FD4F7FD900AAD0D831550A06721F20FF5480D1C3CB`。模型與呼叫的歷史結果保留，不將回復後的 cancelled/stale 狀態改寫成可執行。

## 本輪驗證

- 133 項本機單元／規則回歸通過，不呼叫外部模型。
- 30 項真實隔離 PostgreSQL 測試通過；其中模型輸出為合成回應，不列為真實模型驗收。包含 SA 判斷 NEEDS_INPUT 時仍停在待補正／審查狀態。
- 六項不付費瀏覽器回歸通過，另跳過預設關閉的真實 Copilot 測試。
- 取得明確授權後，單次真實 Copilot 瀏覽器測試通過（26.3 秒）；無自動重試。
- 直接查詢 PostgreSQL，核对呼叫編號、狀態、模型、NEEDS_INPUT、用量與 write_started；事件包含 SA_QUEUED、SA_DISPATCH_RESERVED、SA_VALIDATED_NOT_APPROVED。
- 最後部署後六項不付費瀏覽器回歸再次通過（16.8 秒），真實 Copilot 測試明確跳過，沒有第二次模型呼叫。另以唯讀瀏覽器檢查既有 SA 結果，390px viewport 的 documentWidth=390。

## 後續限制

本次單次驗收當時，Windows Worker 為指定 Task／Run 執行器；後續已補上 [常駐模式與程序 lifecycle 驗證](worker-lifecycle-2026-09-13.md)，沒有因此新增真實模型呼叫。Copilot 只驗證了 SA；Developer、QA 與 Hop/Vertica/Release 尚未完成真實整合。Bedrock 的真實呼叫仍未驗收，隔離部署未取得 AWS 憑證。

P0 仍待完整模型中斷核對 UX／驗收、專案摘要及設定測試記錄；P1–P3 的完整 ETL、四案例、20 案例與成效報告均未達標。
