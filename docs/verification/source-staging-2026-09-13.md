# CSV 執行來源副本：開發驗證

source_staging.stage_csv_source 重新讀取 checksum 綁定的 upload bytes，對同一份 bytes 驗證 CSV，再寫入每次嘗試獨立的私有暫存目錄。輸出僅供內部執行器使用，不得進入公開 API 或 Release。副本不等於執行授權；呼叫端仍須確認目前 Run／規格／人工核准並以唯讀 mount 供 Hop 使用。

31 項本機 staging／integrity／CSV 測試通過：原檔異動不影響副本、同 Run 不同嘗試互不覆寫、離開 context 或例外只清理自身目錄、原檔保留、不合法 CSV 不提供副本。首次以單欄 CSV 變更分隔符作為失敗案例不成立，已修正為標題不符後重跑。

未宣稱可抵抗本機 owner／admin 修改副本。尚未接入 Hop 原生執行測試、Worker、唯讀 runtime mount 或 Vertica。未部署此開發元件；目前服務仍使用前次通過驗收的版本。下一步驗證原生 Hop 確實讀取這份副本，而非重新開啟原始 upload。

## 追加：原生 Hop 副本驗證

- test_source_staging_hop.py 為明確 opt-in（WORKBENCH_NATIVE_HOP_STAGING_TEST=1）的本機 WSL 測試。使用固定合成 compiler fixture，產生 HPL 候選，建立已核對副本後刻意改寫此次測試原始 upload；不改 repository fixture。
- Docker apache/hop:2.12.0 以 network=none 執行；驗證程式與候選 HPL 唯讀掛載，再將副本唯讀掛到固定 SOURCE_CSV 位置。原生 Java probe 將 TableOutput 換成測試收集器並確認無 DB 節點殘留。
- 原生 Hop 實際得到 A|301.35|2、B|300|1、a|110|1，3 筆且 errors=0。副本 bytes 仍與 fixture 一致；context 結束清理副本、不刪原始 upload。
- 1 passed in 5.88s，輸出 HOP_STAGING_PASSED original_changed=true output_rows=3 network=none target=TEST_COLLECTOR。
- 初次測試 Windows 反斜線使 wslpath 回傳失敗，尚未啟動 Docker；改用正斜線後重新執行通過。
- 已驗證的是原生 Hop 使用副本，不是平台 Worker 的授權／staging／Hop 端到端流程。未連接 Vertica、未生成 QA／Release，也未部署 source_staging 進執行服務。
