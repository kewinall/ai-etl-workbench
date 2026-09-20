# 舊版 Release 入口暫停與證據

## 原因

舊 POST /api/tasks/{task_id}/release 僅要求 Task SUCCEEDED、已確認 Naming Contract 及存在產物；沒有 Run/revision/checksum 綁定的 QA 與人工交付核准。舊下載 API 只核對記錄及檔案位置。

release.py 的舊打包器直接收錄歷史 HPL/HWF，掃描跳過 XLSX 與大於 2 MB 的檔案，且並非完整主機、路徑、機密與資料排除驗證。不能將舊 RELEASE_READY 記錄認定為新 Pilot 的核准交付。

## 處理

兩個 Release ZIP HTTP 入口現皆回覆 409 / RELEASE_PIPELINE_NOT_READY。沒有新增可用環境變數绕過的開關。沒有刪除舊 ZIP、SDM、artifact 或控制資料，個別歷史產物介面未修改。

這是暫停不符合規範的舊交付路徑，不是完成 Release 功能。舊打包器暫留於程式庫，尚未改造成新版安全產生器，不可接回正式交付路由。

## 驗證

- test_release_http_gate.py + test_run_api.py：7 passed，1.00 秒。
- 測試抽取 main.py 實際路由函式及裝飾器到隔離 FastAPI；不提供 repo/file 函式，證明阻擋前沒有控制資料或檔案操作。執行開關 true/false 均不能開放舊路徑。
- 部署後實際 HTTP POST 與 GET（不存在的 probe ID）：均 409、相同阻擋碼；未建立任何 ZIP。
- /api/ready：ready，execution_enabled=false。

## 後續必要工程

版本綁定 QA 證據、人工交付核准、核准產物白名單與精確 checksum、可攜化編譯、完整內容檢查（包含 XLSX 內部與大型檔）、原子不可變 ZIP、下載時核准及完整性複驗。上述未完成前不得重新開放 Release ZIP。
