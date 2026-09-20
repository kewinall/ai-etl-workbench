# Worker、私有 Log 與網站整合回歸

## 本輪實測

- 本機後端：300 passed、69 skipped，5.73 秒。排除 test_api.py，資料庫與 native Hop opt-in 關閉；跳過不算驗收通過。
- 已部署網站：12 passed、2 skipped，39.3 秒。跳過付費 Copilot 與 native Worker lifecycle；未新增模型呼叫。
- 規格網站保存／確認／API 回讀：TASK-20260913-0131，Run 0cd41b39-54c1-4f64-a57f-bd8de1347b93，Specification 8b32969a-363a-4f21-9c2a-dbfcccc2c263。
- 真實上傳與換檔：TASK-20260913-0133，原 Run 34bf341b-5214-487d-b20a-8721772c9e1d，新 Run 4e371672-2a18-4daf-b92a-e9dfeca32d6e。CONTROL Worker 讀取實際 CSV，2 筆資料、39 bytes，來源 checksum 8f9a819e68e2b4dcd8d098a7d3a838e144a8cc3fb7c70ff2d38965c93868e8c6。

網站涵蓋專案新增／編輯／取消／重載、歷史 Task 與節點、六頁籤、設定保存、來源換檔、瀏覽器返回與窄版面。部分產物與狀態分支使用合成 API 回應，不是實際 Hop 產物驗收。

## 目前工程界線

後續部署更新：API 與 CONTROL Worker 已更新至含完成結果／Log checksum 關聯檢查、Worker 注入保存函式的新映像。/api/ready 為 ready，運行環境 WORKBENCH_EXECUTION_ENABLED=false、WORKBENCH_SA_DISPATCH_ENABLED=false。部署後專案／歷史 Task／節點、設定政策、來源證據 UI 的四項瀏覽器測試通過（12.2 秒）。下段「尚未部署」為本報告初次回歸時的歷史狀態，以此更新為準。

已加入單次 Worker 編排、執行授權、準備檔案核對、Hop 結果規則、私有 Log 加密與 PostgreSQL migration 032。真實 Hop CLI 已另測 local metadata、CSV Filter/Aggregation 測試接收節點與缺少來源的失敗結果。新完成結果要求對應已保存 Log 的檢查已通過 PostgreSQL 測試，但尚未部署至運行服務。

上述元件尚未形成網站派發到真正資料庫的完整 adapter。Vertica 連線、資料比對 QA、SDM、人工核准 Release、四案例與 20 案例成效報告仍未完成。網站回歸不能取代這些驗收；P0–P3 仍為進行中。
