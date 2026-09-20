# QA 前置 Hop 證據綁定

執行答案選取現在除了 Run 完成狀態，還要求唯一 HOP_EXECUTED_QA_REQUIRED / HOP_EXECUTION 事件，以及保存的私有日誌 checksum。完成事件重新通過 validated_hop_outcome 檢查，事件中的 log checksum 必須與私有日誌一致。缺少或重複事件、缺少日誌或指紋不符均拒絕。

compare_execution_cursor 回傳增加 hop_event_id / hop_log_checksum，使後續保存的比較證據可引用具體執行事件；仍保留 actual_provenance=NOT_VERIFIED 以及 qa_passed/release_ready=false。

## 實测

隔離 PostgreSQL + 合成 Worker/cursor：3 passed、1 skipped，1.51 秒。正常完成綁定事件与日誌，測試修改自身 fixture 的事件指紋後拒絕，finally 恢復原事件。未修改任何使用者 Run，亦未執行 Vertica 寫入；native adapter 測試未啟用。

CONTROL 已恢復。新增 QA 內部模組尚未部署，無公開 QA 執行 API。此檢查比對保存的日誌指紋，尚未在此處解密重驗日誌完整內容；不是實際目標資料來源證明。真實結果查詢與來源綁定、持久 QA、SDM、Release 及 P0–P3 完整驗收仍待完成。
