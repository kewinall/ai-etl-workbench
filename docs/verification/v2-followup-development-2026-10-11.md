# v2 後續開發與驗證

狀態：進行中，第一段部分完成。起點1c3d069。未部署5197／5183，未呼叫模型、Hop、Vertica或Release。

## 已完成與證據

- Task層級POST run／rerun／supplement統一HTTP410 LEGACY_EXECUTION_RETIRED，移除舊API內模型及Hop執行鏈與無引用imports。歷史GET及下載保留。
- PUT Task在repository交易內取得Task row lock，檢查task_run存在；已有版本回409 TASK_VERSIONED_EDIT_REQUIRED，不改寫原需求、來源、目標或事件。與RunQueue建立版本共用同一Task鎖。
- 新增六項HTTP路由測試：派發開關true／false皆410，repository任何存取立即失敗，證明先拒絕後端副作用；一項隔離PostgreSQL版本編輯拒絕測試，完整Task含logs前後相同。
- 首次全套2064pass／139skip／1fail：新增測試誤用不存在的queue.create，改成實際enqueue後重跑2065pass／139skip／0fail／1 dependency warning，50.91秒。
- 隔離Compose project ai-etl-retirement-20261011，PostgreSQL17、internal network、獨立volume，59 migrations；所有外部派發关闭，使用既有regression映像與本機backend唯讀掛載。未宣稱映像重建或真實ETL驗收。
- diff --check通過。既有test_join_replay_worker.py未修改或提交，SHA256 cc1f19bd4e2da5bf311ed3d3f89802f65e497d5fa40e7cc954d32b6a553e9777。

## 第一段尚待完成

逐寫入API核對與直接拒絕驗證；新增靜態inventory JSON作為清單，各項一律PENDING，不能將現有全套測試外推為全部守門通過。
舊requirements/revise已有版本檢查，但仍需審查競態與無版本Task的reset副作用。Hop準備失敗的受控修正版入口尚待補齊。

## 第二、三段

修正空白舊版區與預建舊節點、過時操作指南、未套用設定儲存入口；更新specification-live及skip清單；新版異常分支和新CSV／Excel／Join完整鏈驗收。保留既有Release，不重設或重跑。

## 下一步

依v2-write-api-inventory-2026-10-11.json逐項讀取handler與service，補有效／缺少／失效／跨Run／已交付／重複請求的適用拒絕測試。完成第一段後才進第二段；5197部署仍需沿用有效部署授權。
