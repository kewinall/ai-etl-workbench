# GitHub 乾淨副本部署與持久化驗證

## 範圍與來源

- checkout：`592eab20c88e81278f20f56cb0e7b7e8dcd6d093`，從 GitHub clone 後 fast-forward。
- 未複製原 Pilot 的 .env、機密、資料庫或歷史產物。
- 獨立 Compose project：`ai-etl-clean-deployment`；本機埠 5194。
- 五個 volumes 均為新 project 自己的 volumes，不使用原 Pilot 資料。
- Docker 29.6.2、Compose 5.3.1、WSL RockyLinux9。
- 模型與 ETL dispatch 關閉；只啟動 API、web、PostgreSQL、Control Worker。

## 已驗證

1. 從 checkout 建置 API/web 並初始化成功；API/PostgreSQL health 正常。
2. `/api/ready` 回傳 ready 且 execution_enabled=false。
3. `/api/runtime/workers` 顯示 CONTROL ONLINE，僅代表心跳，不是 ETL 健康。
4. API 建立、修改合成專案 `61f1dea2-8229-4dcc-a5bb-96247382ce74`。
5. 直接 PostgreSQL SELECT 確認 description 為 `Edited before restart`，
   naming_rules 保存 `測試欄位 → test_field`；沒有建立任何 Task。
6. 只 stop/up 此 Compose project，沒有刪除 volume。
7. 重啟後同一 API 逐欄比較 PASS；Control Worker 再次 ONLINE；migration 日誌為 Applied 0 migrations。
8. 真實瀏覽器可見相同專案，設定／歷史頁可切換，「建立 Task」導向此專案的
   獨立建立畫面；瀏覽器返回後回到同一專案歷史頁。未提交 Task。

可重跑持久化檢查（此工具限制本機 5194，且只供上述隔離環境）：

```sh
python scripts/verify-deployment-persistence.py setup \
  --base-url http://127.0.0.1:5194 --receipt outputs/deployment-check.json
# 沿用相同 project name、埠與 Compose 檔案 stop/up 後：
python scripts/verify-deployment-persistence.py verify \
  --base-url http://127.0.0.1:5194 --receipt outputs/deployment-check.json
```

`setup` 收據存在會拒絕，避免無意重建；`verify` 不寫 API。真實測試另證明
指定 5183 會在網路請求前拒絕，不產生收據。

## 限制與後續

- 初次 up 成功後發現 API/web/PostgreSQL 同時正常退出（exit 0）；
  隨後 WSL 查詢時僅自動重啟的 Control Worker 存活。保持一個 WSL 工作階段
  後重新啟動，此問題未再出現。這是環境生命週期的觀察，不宣稱已證明唯一根因。
- 本次用一小時的暫時 WSL keepalive 完成驗證，未修改全域 WSL 或 Windows 開機設定。
  正式啟停與無人值守復原仍屬第 7 階段，不可用本結果宣稱 Windows 重開機驗收通過。
- JDBC 為外部合法取得且 SHA-256 固定的前置檔案；沒有放入 GitHub。
- Vertica server 是另行供應的外部依賴；portability Compose 的本機 image
  前置條件仍明示，並非公開可拉取的完整 DB 環境。
- UI 僅基本部署 smoke；未把全部按鈕、窄版、舊 Task 節點或下載視為完成。
  新建畫面仍呈現多種來源能力，須於第 5 階段與實際支援範圍逐項對齊。
- Worker 乾淨 checkout 完整建置成功，image ID：
  `sha256:f671c18d58b08649592a5e7c11e39b2ffb2dd0fb34f0dbd4a051215fe66fa015`。
  使用同一 checkout 的測試與合成 fixture，在新映像驗證 Hop 正常／錯誤流程
  與 Python 相依版本：4 passed（6.97s），無網路、無 DB 寫入。

## 第 1 階段判定

版本／部署基準通過：source 已上版且可取得、相依前置條件明示、Worker 可從
checkout 建置、隔離回歸與原生測試通過、API／UI／DB 持久化與重啟 smoke 通過。
上述限制仍有效；不代表整體 P0–P3、Windows 開機復原、真實模型／Vertica
全情境或第 2–7 階段已完成。下一步為日期範圍補正與新 revision 真實執行。
