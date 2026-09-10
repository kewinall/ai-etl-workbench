$body=@{name='客戶 CSV 驗證展示';requirement='讀取客戶 CSV，清理後寫入 PostgreSQL 前 10 筆有效資料';source_type='CSV';model='codex_cli'}|ConvertTo-Json
Invoke-RestMethod 'http://127.0.0.1:8765/api/tasks' -Method Post -ContentType 'application/json' -Body $body
