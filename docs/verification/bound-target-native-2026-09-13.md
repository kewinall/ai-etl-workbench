# 真實 Run 目標隔離、空表與來源核對

## 本輪結果

- Project：`3b44fc01-bc1e-4d1f-b949-99fb9cf945f4`
- Task：`native-pilot-5c8607a94e3e42b2afd9703d35beef06`
- Run：`7fc2be0d-f1a8-4ea5-a9ed-74107369001b`
- 新建合成表：`ai_sample.pilot_5c8607a94e3e42b2afd9703d35beef06`。沒有 DROP 或覆寫舊表。
- 固定案例仍為 A 101.25／A 200.10／B 99.00，Filter >100、分組 SUM／COUNT；真實 Hop 寫入後，獨立連線讀回 A／301.35／2。
- Hop 私有日誌 SHA256：`b1d7ed959681f64b352ce4e0cbe09437ee9b28480b4bcc013e3f019c8367a94c`。只在記憶體比對，確認原始密碼不在日誌中；未公開日誌。
- 結果比對 ID：`58731bad-935c-47a2-8808-a0bc5cbf8afc`；MATCH。
- 核准查詢 checksum：`8ea6bee3c5aced9fcd803966fdd7b29f396d4c5cc43e37fb534edd892c6e956a`。

## 已驗證的證據鏈

PostgreSQL 保存的事件 ID 及時間先後符合：TARGET_CLAIMED → TARGET_EMPTY_CONFIRMED → WRITE_STARTED → HOP_EXECUTED_QA_REQUIRED → RESULT_COMPARISON_RECORDED → RESULT_SOURCE_BOUND。

受控來源讀取程式自行取得 Run 設定快照、指定版本機密與編譯器查詢；呼叫者不能提供 SQL 或 cursor。讀完後重新檢查綁定，另存不可變來源證據，保留原始比對紀錄，不改寫舊 evidence。

- 新 Run 的來源狀態為 BOUND_PLATFORM_TARGET；scope 僅 PLATFORM_MANAGED_TARGET。
- 舊 Run `65269428-7e6c-434b-a16e-5d557608f184` 缺少執行前證據，實測拒絕提升來源狀態。
- 已有結果的表再次做唯讀空表檢查時，實測拒絕 PILOT_TARGET_NOT_EMPTY；沒有呼叫 Hop 或修改資料。
- 重複讀取／保存仍是相同比對 ID，RESULT_SOURCE_BOUND 只有一筆，WRITE_STARTED 只有一筆。

## 驗證範圍

- 後端完整回歸：582 passed／84 skipped，5.86 秒。跳過項目不能算整合通過。
- PostgreSQL 目標與空表紀錄約束：1 passed，0.36 秒；涵蓋不可更改／刪除／執行後補登，合成交易全部 rollback。
- 部署後瀏覽器：2 passed，6.4 秒。真實案例來源證據 API／顯示／重載／390px，以及合成舊產物六頁籤回歸；Release API 仍 409、無 ZIP 連結。
- 先前在掛載新 migration 後直接恢復舊映像，安全遷移器拒絕缺檔版本；已重建包含完整 migrations 的 API／Worker 並恢復 CONTROL，API healthy。之後採先 build 再 up，避免映像與 schema 分離。
- 空表檢查依 Vertica skill 的 SQL 指引與 24.4.x 官方 LIMIT 段落（PDF p.3638）核對；實際相容性以 Vertica 25.3 實測為準。驅動 timeout 依已安裝程式碼確認 socket timeout 使用 connection_timeout=10。

## 明確限制

這不是完整 P1：仍由內部 opt-in runner 建立／核准輸入，AI Profile 為合成，不新增模型用量；網站尚無正式派發 Hop 的完成流程。qa_passed=false、release_ready=false；正式 QA 核准、同 Run SDM／Release、P2/P3 未完成。

平台目標登錄不保證外部 DBA 或其他程式沒有直接修改資料庫；本 Pilot 假設平台管理範圍沒有外部寫入。空表證據僅可在保存後五分鐘內用於啟動 Hop；不可變證據不會被偷偷更新。超時後需要新的 Run 與目標，不自動重跑寫入。

API 與常駐 CONTROL 的 execution_enabled=false；真實模型 dispatch=false。此次沒有刪除既有 Windows 資料／產物，也沒有 Git push。
