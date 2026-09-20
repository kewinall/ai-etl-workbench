# 已保存 Vertica 連線確認

使用者已確認完成設定，並同意正式 SDM renderer 使用既有 openpyxl；先前待確認狀態已解除，SDM 實作仍未完成。

## 實測

- vertica-default 必填連線欄位已保存，Port 5433。
- connection 機密已存在，平台可以解密。未輸出密碼。
- 從實際 API 容器使用已保存設定及憑證，嘗試一次 verify-full 唯讀 SELECT version()，結果 ConnectionError，未執行寫入、未降級 TLS 或自動重試。
- 隨後對同一設定目的地做 TCP 診斷，結果 ConnectionRefusedError，errno 111。
- 設定 host 為 loopback。API 執行在容器內，因此這個位址指向 API 容器本身，而不是 Windows 或另一個資料庫容器。
- 本機 Docker 有運行中的 vertica-25.3 容器，公開 Port 5433；這不等於已確認它就是使用者指定的驗收目標，也不證明 DB 已就緒。

## 下一步

確認預期目標是否為本機 vertica-25.3，再選擇 API 可達的容器網路／主機位址，重做唯讀連線驗收。不自行更換目標、修改密碼、關閉 TLS 或開始 ETL。測試寫入範圍仍需明確。

官方 Python driver TLS 參考：https://github.com/vertica/vertica-python#tlsssl 。本次故障在 TCP 階段，不能據此判斷密碼或憑證有問題。
