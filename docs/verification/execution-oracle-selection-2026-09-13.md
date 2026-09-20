# 執行後固定答案選取

新增內部 load_execution_oracle：Task lock 內確認 Run 為 NEEDS_REVIEW / HOP_EXECUTION / HOP_EXECUTED_QA_REQUIRED、write_started、租約已解除；由單次 reservation 和 v2 授權取得固定 oracle ID，不查最新答案。重新核對 binding checksum、規格歸屬、答案版本與核准指紋，最後解密及驗證文件。

回傳 EXECUTION_ORACLE_PINNED_NOT_COMPARED，qa_passed / release_ready 永遠 false。原始答案只供內部後續比對使用，未新增 HTTP 入口。

隔離 PostgreSQL / 合成 Worker：3 passed、1 skipped，1.53 秒。驗證執行前拒絕、合成完成後取得授權內答案、失敗／不明／準備失敗拒絕。跳過 native Hop adapter；不是實際 ETL QA 驗收。

本函式尚未部署或接入真正結果查詢；CONTROL Worker 已恢復原服務。仍須建立真實 Vertica 結果來源與持久 QA 證據、SDM、Release 及四情境／20 案例。未新增模型請求、Vertica 連線或寫入。
