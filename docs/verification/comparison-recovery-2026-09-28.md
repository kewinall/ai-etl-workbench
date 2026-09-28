# 結果比對恢復：工程與隔離驗證（2026-09-28）

## 判定

已實作明確核准的「只重新比對、不重跑 ETL」流程，通過隔離 PostgreSQL、API、
瀏覽器互動及回歸測試。**本輪尚未部署正式 Pilot，也未恢復真實 Excel 案例；
不代表 Excel QA／Release 或第 5–7 階段完成。**

## 行為與不變條件

- `GET/POST /api/tasks/{task_id}/runs/{run_id}/comparison-recovery` 提供目前版本的確認與排隊。
- 新增 migration `057_comparison_recovery.sql`。原 `hop_dispatch_request` 的
  NEEDS_REVIEW／失敗原因與事件完全保留，不改成成功。
- 只接受原 Hop 已知完成且有單一完成事件、私有 log、原執行核准及 reservation 的 Run；
  原派發必須已結束，且失敗原因為後處理／比對失敗。結果未知、活躍 lease、上游變更均拒絕。
- 綁定 request、規格、輸入／設定、Naming Contract、答案、原執行／日誌／查詢指紋。
  任意 SQL、使用者自填 PASS 或替換答案不在此 API 中。
- Task row lock、唯一 Run／原派發鍵與條件式領取防止重複請求；同一請求只被消費一次。
  原 Hop Worker 優先處理此讀取工作，處理後直接返回，不進入建表或 Hop 執行分支。
- 僅使用既有受控目標擁有權、空表前證據、一次 WRITE_STARTED、原 compiler-pinned SELECT。
  讀取前後核對版本，保存 comparison／provenance，再保存獨立恢復完成紀錄。
- 不一致結果照實保存；恢復完成不等於 QA PASS。QA 在恢復未完成或指定非恢復比對時停止。
- Release 只新增可驗證的成功恢復 lineage，仍要求真實 SA／Developer、QA 核准、SDM、
  可攜重播與原交付檢查。缺來源證據、不一致、恢復失敗不能走此交付途徑。
- 不自動重試。Worker 若在 CLAIMED 後失聯，保留未知狀態，不能重新派發原 ETL；
  本輪未宣稱已完成恢復 Worker 的程序死亡／重新領取驗收。
- 停機檢查已納入 QUEUED／CLAIMED 比對工作；不能忽略它們進行已認證停機。

## 驗證證據

| 驗證 | 結果與範圍 |
|---|---|
| 新流程隔離 PostgreSQL／API | 12 passed：一致、不一致、讀取失敗、前後版本變更、結果未知、active lease、命名變更、缺完成事件、跨 Task、重複請求、錯誤領取者與不可改寫歷史 |
| 最終完整後端回歸 | 1702 passed、106 skipped、1 warning；40.04 秒，exit 0 |
| Windows 停機保護＋來源發行檢查 | 16 passed；4.92 秒 |
| 瀏覽器合成互動 | 4 passed；8.5 秒：MATCH／MISMATCH／FAILED／409、勾選確認、重載、單次 POST、390px 無橫向溢出、無頁面錯誤 |
| 前端及 Docker 建置 | 通過；前端 517.06 KB 大型 bundle 警告仍存在，不是功能失敗 |

新流程測試使用真實隔離 PostgreSQL，但 Hop engine、Vertica cursor 與角色資料是明示合成替身，
不能當作真實外部執行驗收。第一輪 4 項新測試失敗，定位為 rollback fixture 共用交易造成
`now()` 的 WRITE_STARTED 時間早於 `clock_timestamp()` 的空表檢查。僅修正 fixture 的事件
時間建模；正式來源證據檢查沒有放寬，之後完整回歸通過。

106 項 skipped 包含需明確原生 Hop、既有真實執行、PowerShell 或其他隔離服務的測試；
沒有將 skip 算成通過。Windows 停機測試另行實際執行上述 16 項。

## 正式部署與下一步

1. 重新建置最新 API／Worker；本輪初次 Docker API 建置早於最後補上的 QA gate，
   不可直接把該舊映像當作最終版本。前端映像已含此次 UI。
2. 檢查既有執行、原生程序與容器皆無進行中的工作，保留控制 DB 備份，
   執行 additive migration 057；舊 DB 缺此表時，新停機檢查會拒絕認證，不能略過。
3. 保持既有四項 execution／SA／Developer／QA 啟用設定，更新指定 API、control-worker、web；
   不重新建立 DB、移除 volume 或重跑既有 ETL。
4. 只對已保存的新 Excel 補正版，透過正常網站確認／API 排隊，啟動 scoped Worker 消費一次；
   核對原失敗紀錄、WRITE_STARTED 仍為 1、新 comparison 與 provenance、Vertica 固定答案。
5. 接續真實 QA、SDM、獨立目的環境 HWF 可攜重播及 Release ZIP，保留全部先前歷史。

回復方式：新恢復請求尚未排隊時，可保留 additive table 並回復已知 API／web 映像；
若已有恢復或交付紀錄，先停止新操作並核對狀態，不刪紀錄、不回復 DB 覆蓋新證據、
不重跑原 Hop。此限制不是自動 rollback／程序死亡恢復驗收。

人工基準維持未量測；原凍結 20 案分母未變。knowledge-workspace WS-0007 最新讀取仍為舊階段紀錄，
既有寫入限制未繞過，本輪尚未持久化至 knowledge-workspace；具權限時應同步本文件及具體下一步。
