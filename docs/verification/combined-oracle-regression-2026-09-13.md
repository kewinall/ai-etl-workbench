# 答案與比對證據整批回歸

## 本輪實測

| 範圍 | 結果 | 限制 |
|---|---|---|
| 已部署網站全部 Playwright | 26 passed / 2 skipped，51.6 秒 | 含真實 UI/API/PG 及合成展示；跳過付費 Copilot、native Worker lifecycle |
| 本機安全後端套件 | 397 passed / 73 skipped，5.38 秒 | 排除舊 test_api.py 主機 DB，未啟用外部整合 |
| 隔離 Compose PostgreSQL integration 選集 | 60 passed / 1 skipped / 409 deselected，10.13 秒 | 真實控制 DB、合成模型／executor；跳過 native adapter |
| 原生 Hop CLI、metadata、固定資料 staging | 4 passed，16.56 秒 | 無網路、測試結果收集器；不是 Vertica 寫入 |

上述範圍彼此重疊，不累加為成功案例數。沒有新增模型呼叫或 Vertica 連線／寫入。

真實網站規格／答案案例 TASK-20260913-0205，Run 56969eac-7503-4f27-b186-a51ae4c003bb；來源換檔 TASK-20260913-0207，新 Run 3801ee62-b7cf-44fc-9e8b-cd7d60f2eb1f。測試恢復原連線設定，保留自身歷史，取消自身未寫入 Run；整批 DB 測試後恢復 CONTROL。

## 完成邊界

此次未發現回歸失敗，但不表示 P0–P3 已完成。真實 Vertica 結果來源／查詢 adapter、正式 QA 核准、SDM／Release、四情境 E2E、20 案例及人工基準仍缺。需要有效的 Vertica Profile 與明確 Pilot 測試表寫入範圍才能做真實整合；未取得前不使用開發機隱含連線，也不將合成證據標示為正式 QA。
