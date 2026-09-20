# 設定解析部署與回歸

## 修正

execution_settings.resolve_settings 對非物件的 Task overrides、AI 策略與資料連線設定明確回傳 BLOCKED，沒有可執行 snapshot。錯誤只包含分類與代碼，不回傳損壞的設定值。明確指定空白、不存在的連線不得退回 Project 預設。

## 實測證據

- 設定解析單元測試：24 passed。
- 安全後端回歸：507 passed、78 skipped（5.61 秒），排除 legacy test_api 及外部整合；不是完整 E2E。
- API 映像重建部署完成；映像 config SHA256：44d5fa5036cb2bc345ba2e8aeec91e76dee233695c2c3751451e4fb1721d1d77。
- 部署後 PostgreSQL queue + project summary：19 passed（2.64 秒）。測試暫停控制 Worker，完成後恢復；僅操作隔離合成資料。
- 瀏覽器完整套件：27 passed、2 skipped（約 1 分鐘）。含真實控制 API/PG 測試及合成回應 UI 邊界測試，不等同真實模型或 ETL 驗收。
- 規格回讀案例：TASK-20260913-0244，Run ae451cdd-bacc-4eb4-bb04-bec2db0d524c，Specification 1386355e-8d00-4395-929d-a6f8f0f55527。
- 上傳與補正案例：TASK-20260913-0246，Run 70aec6fa-feb4-4538-a1d2-3aded85bcfaa，補正 Run d6834db9-c088-496d-a149-b11e10788349。
- 部署後 API healthy、CONTROL Worker Up、web Up，網站 localhost:5183。

## 限制

本輪未呼叫模型，未執行 Hop 或 Vertica。部署保持 SA dispatch 與 execution 關閉。P1 真實整合、P2 四情境與 P3 成效評估仍未完成；正式 SDM renderer 選擇待使用者确认，未將自動 continuation 視為同意。
