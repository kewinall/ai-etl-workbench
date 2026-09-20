# 標準答案歷史 API 驗證

新增按 Task / Run / Specification 範圍查詢版本的 GET API（oracle router factory）。僅回傳版本、checksum、建立時間與核准 metadata，不讀取或回傳答案資料列、nonce、密文。

`approval_recorded` 表示曾保存核准；`eligibility=NOT_EVALUATED` 明確表示未判定目前執行資格。清單不授予 QA 或 Release 通過。

## 驗證

- 本機 API、文件格式與加密回歸：22 passed，0.36 秒。
- 隔離 Compose PostgreSQL + FastAPI：5 passed，1.08 秒；覆蓋兩版本排序、新版本不繼承核准、跨 Task 拒絕、上游規格改版後歷史仍可讀、新規格清單為空，以及精確 metadata 欄位白名單。
- 測試直接唯讀掛載目前 app / tests，未以舊映像程式冒充新程式驗收。CONTROL Worker 測試期間停止，測試後恢復。

## 未完成範圍

上述初次 API 驗證時 Router 尚未掛載正式 main.py。後續已完成以下部署與網站查閱驗證，保存／核准表單仍未接通。

## 後續網站查閱部署

- main.py 掛載 oracle router；Task「執行與 QA」新增答案歷史區，保留既有執行／Hop Log。
- 支援 Run／規格選擇、版本指紋、保存及核准時間；讀取錯誤與空清單分開呈現，提供重新讀取。
- `npm run build` 通過，API／web／CONTROL 已重建部署。
- Playwright：2 passed，6.7 秒。涵蓋合成答案歷史錯誤重讀、切換規格清除舊資料、核准不冒充有效資格、390px，以及既有六頁籤、節點、下載契約。
- 答案資料為 browser fixture；Project／Task 建立為隔離平台 API。不能當作真實標準答案保存 UI 或 Vertica E2E 證據。

尚未完成真實 Vertica 答案比對、QA、SDM 或 Release。沒有新增模型呼叫或 Vertica 寫入。
