# 已核准規格與來源準備整合

prepare_approved_source 沿用資料庫最新版規格與人工核准驗證，讀取 Run 的 upload 綁定，在獨立 attempt 目錄保存已驗證 CSV。文件 I/O 不持有資料庫鎖；副本完成後再次查核目前規格／核准／Run／命名／設定，再保存 checksum 相符的 HPL 候選。

內部結果包含 Run、specification、approval、input、settings、HPL 與來源 checksum，execution_authorized=false。路徑僅限執行器內部，不得暴露 API 或放進 Release。此準備結果仍不能跨交易充當執行許可；dispatch 前需原子鎖定授權並重新核對。

11 項隔離 PostgreSQL 準備／核准候選／規格 API 回歸通過（2.29 秒）：正常核准可準備 byte 與 HPL、準備途中取消 Run 會被第二次檢查拒絕、兩種情況結束均清理自己的目錄且保留原 upload。未呼叫模型、Hop 或 Vertica。

本次新映像僅供測試，API 容器未重建；原 CONTROL worker 已恢復。尚未接入真正 dispatch、Hop 連線、Vertica、QA／SDM／Release，不是 P1 完成證據。
