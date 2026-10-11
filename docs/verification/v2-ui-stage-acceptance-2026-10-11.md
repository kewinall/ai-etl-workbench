# v2 七階段介面收斂：階段性工程驗收 — 2026-10-11

後續更新：新版 5197 已部署基準 3f1a312，限定唯讀回歸通過，見 [部署驗收](5197-deployment-acceptance-2026-10-11.md)。下方保留當時工程驗收的邊界。

## 判定與範圍

**本階段工程驗收通過，可以階段性上版；整體 v2／WS-0007 維持部分完成。**

驗收程式基準為 `7d88985483d1132d53679143bd0bc83824f3ac3c`，涵蓋七階段共用 Run、唯讀狀態與操作資格、介面精簡與管理入口、舊元件整理、規格刷新競態、歷史時間軸及規格保存／核准的同 Run SA 守門。

三個指定 CSV／Excel／Join 真實案例已有正式交付證據；本輪只 GET 回歸保存產物，不重跑。這些案例的既有全鏈證據與新版未部署介面的工程驗證分開判定。

## 驗收依據

| 項目 | 本輪獨立證據 |
|---|---|
| 建置與基本檢查 | 前端 build、diff check PASS |
| 隔離 PostgreSQL 17 後端 | 2056 passed／141 skipped，0 failed |
| 預設瀏覽器回歸 | 97 passed／39 skipped，0 failed；含窄版及鍵盤 |
| 刷新與時間軸 | 原 V1/V2/V4、6 項可控時序測試、2 項時間軸測試通過 |
| Excel／JSON 合成操作 | opt-in 2 passed；沒有模型或 ETL |
| SA 守門 | 有效 200；缺少／失效／他 Run 409；拒絕後紀錄數不增 |
| Developer 完成時失效 | CSV／Join 不保存新規格；既有 SA 重驗機制確認 |
| 正式交付保護 | 三 ZIP 指紋一致、updated_at 不變、每案 WRITE_STARTED=1 |

詳見 [第三輪獨立驗證](codex-round3-review-2026-10-11.md)、[第二輪獨立驗證與原缺陷](codex-round2-review-2026-10-11.md)、[工程與各輪修正紀錄](ui-simplification-2026-10-11.md)。跳過的測試不算通過；現有結果不是新 Dockerfile 乾淨重建或新版部署驗收。

## 不納入完成宣告的項目

- 5197 尚未部署最新程式；仍維持先前版本。5183 不變。
- `specification-live.spec.ts` opt-in 舊入口與 SA fixture 尚待更新。
- 其他寫入 API 的直接拒絕覆蓋尚未逐一完成。
- JSON／資料表完整模型、Hop、Vertica、QA、可攜 ZIP 全鏈及其他 WS-0007 未完成里程碑。
- 已交付版本建立修正版仍受既有後端限制，不新增此能力。

## 上版與接續

使用者本輪明確授權現有成果更新 repo。既有尚未推送的分段提交保留，驗收與 Codex 文件另作文件提交；不提交既有 `backend/tests/test_join_replay_worker.py` 工作樹修改，也不提交 runtime-temp、ZIP、密鑰或本機部署秘密。

GitHub 發布是程式與證據保存，不代表新版網站已部署。下一步先修正 opt-in 規格操作測試，Codex 隔離重驗；取得部署授權後才重建 5197 api/web，並以 GET-only 驗證舊交付。保留原核准、歷史結果與舊目標，不重跑已交付 ETL。
