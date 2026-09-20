# 答案型別可表示性

已部署後端保存／核准驗證及前端輸入檢查：NUMERIC(p,s) 不接受需要改值的四捨五入或 precision overflow；忽略不改變值的尾端零。VARCHAR(n) 檢查 UTF-8 位元組而非字數；BIGINT 拒絕 Vertica 保留的 -2^63。現有通用 multiset comparator 仍為通用 signed 64-bit 比對；Vertica 特定限制在答案與編譯契約驗證層執行。

## 文件依據與政策

使用 vertica / vertica-sql-loading 離線技能檢索 [Vertica 24.4.x 官方文件](https://docs.vertica.com/24.4.x/en/vertica_doc.pdf)：

- PDF p2458，INTEGER／NUMERIC：-2^63 保留 NULL；precision 是總位數；超出 scale 會 rounding。
- PDF p2429，CHAR versus VARCHAR／Setting maximum length：長度以 octets 計算，UTF-8 每字元可能需要多個位元組。

平台採更嚴格的「答案值不可被默默四捨五入或截斷」政策；不是宣稱所有上述值都必然遭 DB 拒絕。此為 24.4.x 文件查證，未連線偵測實際 Vertica 版本，不能算執行環境相容性驗收。

## 驗證

- 初次測試揭露 TEXT／STRING 分支名稱不一致，修正後 29 passed，0.81 秒。
- 前端序列化 3 passed，372 ms；建置通過。
- 真實隔離 PostgreSQL 保存與核准測試 1 passed，1.11 秒，含拒絕超長中文與多餘小數位。
- API／web／CONTROL 已重建部署；合法答案真實 UI → API → PostgreSQL 保存、核准、改版及回讀 1 passed，7.3 秒。
- Task TASK-20260913-0194，Run b1065406-01cf-4dfd-953e-93496dbe2b61，規格 80467f44-3190-4f1d-89e8-9d7ced6cea3e。

未修改既存答案內容；舊資料仍可唯讀查閱，未因此授予 QA／Release。未呼叫模型或連接／寫入 Vertica。來源資料及真正目標結果的同等型別驗證、真實 QA、SDM、Release、四情境與 20 案例仍待完成。
