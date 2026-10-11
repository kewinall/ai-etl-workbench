# Codex 第三輪獨立驗證 — 2026-10-11

## 結論

HEAD `7d88985483d1132d53679143bd0bc83824f3ac3c` 的三項補正通過本輪獨立驗證。這是隔離工程驗證，尚非新版 5197 部署驗收；WS-0007 維持 active/部分完成。未修改應用程式、未推送、未部署、未呼叫模型、Hop、Vertica 或 Release。

## 本輪實際結果

- `npm run build` PASS（僅 >500KB bundle 提示）；`git diff --check` PASS。
- 專用 Docker PostgreSQL 17 tmpfs、59 migrations，既有 regression runtime image 加目前 backend/config/database 唯讀掛載；所有外部派發關閉。非全新 Dockerfile 映像重建驗收。
- 後端全套：2056 passed / 141 skipped / 1 dependency deprecation warning，49.79s。與前輪同類環境 2048 相比 +8；不能等同 Claude 雲端計數。
- 完整預設 Playwright：97 passed / 39 skipped / 0 failed，2.7m；含規格 V1/V2/V4、六項刷新競態、兩項時間軸，以及 390/768/1440px 與鍵盤場景。主要使用合成瀏覽器回應，不代表真實模型/ETL 驗收。
- Excel/JSON opt-in：2 passed，20.6s。指定本輪臨時容器，合成 SA 核准、確定性 CONTROL 檢查；無模型或 ETL。預設回歸留下的一筆 approved QUEUED Run，先按精確 Run ID 限定做一次確定性檢查（NEEDS_INPUT），沒有啟動通用 Worker。
- 第二個獨立 PostgreSQL 補測規格核准 API：有效 SA 200；缺少、失效、只有他 Run 核准皆 409，原因碼正確。三種拒絕前後規格/核准/規格事件均維持 1/0/1；再次保存也拒絕且計數不變。有效核准後 1/1/2。缺少/他 Run 情況以測試專用 direct store 模擬新守門規則前的歷史規格列。
- Developer journal + SA prerequisite 額外重驗：11 passed，6.09s。包含 Developer 上游變更後 CSV/Join 回傳 STALE_RESULT_NEEDS_REVIEW，沒有保存規格。

## 交接紀錄需更正

Developer 並非只在預約時檢查 SA：`DeveloperJournal.finish` 在 Task 鎖/同交易內重新呼叫 `developer_contract.load_context`；該函式重新計算 SA binding 並比對同 Run approval/binding_checksum。失效結果保存為歷史紀錄，沒有新規格。雖未直接呼叫新的 `require_current_sa`，不能據此宣稱缺少完成時的 SA 檢查。

## 未完成及下一步

- `specification-live.spec.ts` opt-in 仍使用舊入口且未取得 SA；本輪預設跳過，不能宣稱它通過。下一步由 Claude 改走七階段、使用隔離合成 SA，保留原業務斷言，再由 Codex opt-in 驗證。
- 其他寫入 API 尚未逐一做直接呼叫拒絕實測；不把本輪規格守門結果外推到所有 API。
- 新程式未部署 5197。待使用者授權 api/web 重建後，驗收新版實際畫面；只 GET 已交付案例，不重跑舊 ETL。
- JSON/資料表完整模型/Hop/Vertica/QA/交付仍未驗收；JSON opt-in 僅驗證來源契約、修訂與設計操作。

## 保護與證據

- 5197 三案 ZIP GET 調查：CSV 10417 / Excel 11152 / Join 10585 bytes，SHA256 與既有紀錄一致；每案 WRITE_STARTED=1，讀取前後 updated_at 不變。詳細結果 `runtime-temp/codex-round3-review/release-get-readback.json`。
- 既有未提交 `backend/tests/test_join_replay_worker.py` 保留，SHA256 `cc1f19bd4e2da5bf311ed3d3f89802f65e497d5fa40e7cc954d32b6a553e9777`。
- 前輪未提交驗證文件保留，SHA256 `da38b6de13de4f79c0cd04e3f49e3959350b4d3d46f6137a8dbb37610793957e`。
- 私有補測程式及讀回在 `runtime-temp/codex-round3-review/`；本文件新增未提交，不更改 Claude commits。

## 清理與 Workspace 讀回

本輪 Vite 5199、兩個專用 PostgreSQL tmpfs、臨時 API 與兩個測試網路已移除；5197/5183 原服務未更動。WS-0007 的 tasks.yml、CURRENT.md 與新增交接 `.workspace/handoff/sessions/2026-10-11-v2-codex-round3-verification.md` 已同步至 knowledge-workspace，最終 commit `bb9f43dfcd06df383ed1cfa06f0c130bb0ec5993`；三檔完整內容讀回一致。應用程式 repository 沒有提交或推送。
