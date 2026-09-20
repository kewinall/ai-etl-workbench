# 查詢指紋部署後網站合併回歸

## 實測結果

31 個案例：重跑 29 passed、2 skipped，約 1 分鐘。整批包含 Project 新增／編輯／草稿保護／摘要／歷史、設定保存重載與錯誤提示、Task 版本切換及核准、規格、上傳、節點及既有產物顯示契約。部分錯誤分支為合成 API 回應，不是原生 ETL 證據。

首次結果：28 passed、1 failed、2 skipped。失敗測試 project-history-filter 使用未存入 DB 的合成 Project，未攔截新增的 summary API，出現額外 404 alert，導致單一 alert 定位不成立。修正只補齊合成 summary 回應；未移除或弱化產品錯誤提示。隨後重跑完整套件通過。

## 可追溯控制流程

- 規格：TASK-20260913-0271；Run 5515a02d-a1f0-4f2f-979c-6f42f83d1539；Specification bbb91f19-bbfd-4b51-9acf-230b4a50a810。
- 上傳：TASK-20260913-0273；Run cbb993c1-b9e6-48fc-ad68-640d03a4bb8e；補正 Run 071ee959-1559-4c28-86a7-29dc41c33b24。
- CSV 39 bytes、2 筆，UPLOAD_BYTES_VERIFIED；execution_authorized=false。不是 Vertica 寫入成功。
- 之後唯讀 /api/ready 再確認 status=ready、execution_enabled=false。

## 未驗收與待確認

真實 Copilot 呼叫及 native Worker lifecycle 案例未啟用；本輪無新增模型呼叫、Hop 執行或 Vertica 寫入。缺少可用 Vertica Profile 及明確批准的測試表範圍，不能開始真實 P1 寫入驗收。正式 SDM renderer 工具選擇仍待確認。自動 continuation 不等於這些授權。

查詢計畫仍需 Run 專屬目標／來源證據與受控查詢 adapter。P1 端到端、P2 四情境、P3 20 案例及人工基準均未完成，不能以本次瀏覽器通過數替代。
