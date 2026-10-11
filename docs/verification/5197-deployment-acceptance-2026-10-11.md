# 新版 5197 部署驗收 — 2026-10-11

## 結論

**部署驗收通過（限定已交付案例的新介面及唯讀回歸）。** 使用者授權「請繼續新版 5197 部署驗收」，程式基準 `3f1a31200cc5b5439d25cd0eba450800b76e3b5d`；只重建 api/web。整體 v2／WS-0007 維持 active/部分完成。

## 部署與版本證據

執行既有 stage-guidance + ui-acceptance compose，指定既有验收專案 `346e9419-4b0e-4ba7-ad29-1756ca7da833`，`up -d --no-deps --build api web`。api 健康檢查 PASS，`GET /api/ready` 為 ready。既有授權派發設定保持不變，`execution_enabled=true`，本輪未產生任何派發或執行意圖。

前端實際 assets：`index-szNnDKAI.js`、`index-L6lnu_sw.css`。容器內 specification_store/workflow_status/developer_journal SHA256 與本機來源完全一致；新 api/web image、容器 ID 及時間記於 [讀回證據](5197-deployment-readback-2026-10-11.json)。Dockerfile api 僅複製 backend/app，不包含原有未提交測試修改。

## 真實網站验收

| 項目 | 結果 |
|---|---|
| 三案 CSV／Excel／Join，390／768／1440px × 七階段 | 63 個頁面 PASS；無橫向溢出、頁面錯誤或 API 讀取失敗 |
| 狀態、責任人與下一步 | 同一 Run、已正式交付；所有寫入操作資格停用，下載可用 |
| 正式交付頁 | 主區顯示 ZIP 與保存 Manifest 文件清單；18 項 ZIP 成員的大小／可用指紋一致 |
| 鍵盤下載 | 9 次 Enter 下載成功，ZIP 指紋符合保存紀錄 |
| 共用刷新與歷史 | 時間軸跟隨共用更新、正常時無獨立刷新；無「後續流程尚未接通」舊文案 |
| Join 歷史 Run | 跨階段、重載、Back 保留同一歷史版本 |
| 管理與手機 | Enter 展開／Escape 收合回焦點；isMobile 390px，階段 Home／End 保留 Run |
| 寫入及錯誤 | 瀏覽器攔截所有非 GET；寫入請求 0、頁面錯誤 0、API 讀取失敗 0 |

只在下載、查看、導覽與 GET 刷新操作，不送出核准、模型授權、Hop、QA、可攜驗證或 Release 請求。

## 原資料及部署保護

部署前後、全部瀏覽器測試後再次讀取：三新案例和兩舊案例共五個正式 ZIP 指紋、Run 完整 JSON 指紋、updated_at 及 WRITE_STARTED 均不變，每案原始寫入一次。三新案 ZIP 為 10417／11152／10585 bytes；舊 CSV／Excel 為 10452／11208 bytes。

八個受保護容器的 ID、image ID 與 StartedAt 完全不變：5197 PostgreSQL、控制 Worker、證據橋、可攜 DB，以及 5183 api/web/PostgreSQL/控制 Worker。未重建這些服務、未修改資料庫、未升級 5183、未重跑已交付 ETL。

原有 `backend/tests/test_join_replay_worker.py` 修改未提交，SHA256 仍為 `cc1f19bd4e2da5bf311ed3d3f89802f65e497d5fa40e7cc954d32b6a553e9777`。

## 證據及邊界

- [機器讀回](5197-deployment-readback-2026-10-11.json) 包含前後五案、63 視圖、操作資格、來源 SHA、手機與保護容器。
- 私有重驗程式與截圖：`runtime-temp/codex-5197-deploy/`；未提交 ZIP、秘密或本機認證。
- 驗收腳本第一次把純服務資格（没有 enabled 欄位）當成停用操作而停止；已依實際 API 型別分開處理，寫入停用斷言保留。不是產品錯誤。證據彙整的 Windows cp950 讀取錯誤已改明確 UTF-8，完成重讀。
- 本輪無合成 API 替代真實案例；也沒有在 5197 直接呼叫寫入 API 來探測拒絕，這仍依先前隔離證據及待補測清單判定。
- `specification-live.spec.ts` 舊入口／SA fixture、其他寫入 API 逐一拒絕、JSON／資料表完整全鏈與其他 WS-0007 里程碑仍待完成。此次不以交付頁通過宣稱全部 v2 完成。

## 回復與下一步

已保留部署前映像 `ai-etl-workbench-api:before-3f1a312`、`ai-etl-workbench-web:before-3f1a312`。需要回復時，在確認沒有在途操作後將這兩個映像重新 tag 為各自的 `:stage-guidance`，再用同兩份 compose 執行 `up -d --no-deps --no-build api web`。不修改 volumes、Worker 或資料庫，也不逆向 migration。本輪未執行回復。

下一步：使用者可在 5197 檢視三案交付頁；Claude 接續修正 opt-in 規格操作測試，Codex 在隔離環境重驗，並繼續剩餘 API 資格拒絕覆盖。部署與發布記錄同步 WS-0007，保持 active。
