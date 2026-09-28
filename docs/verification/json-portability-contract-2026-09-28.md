# JSON 可攜證據契約（2026-09-28）

本階段只完成證據驗證與 Release 核准端綁定，未接重播 Worker、未部署正式、未完成 JSON 可攜交付。

- PortabilityEvidenceV5 明示 JSON 格式、原始檔指紋、BOM 讀取副本資訊與 launcher receipt。
- 核准端確認執行授權中的原檔／Profile／契約與規格一致，再檢查獨立重播的讀取副本及 log 指紋。
- CSV／Excel 證據不能代用；缺少讀取副本、錯誤格式、改變政策或 receipt（即使重算 checksum）均拒絕。
- receipt 的 qa_passed 必須為布林 false，僅代表啟動設定，不能視為 QA 通過。

測試：35 項 JSON／Excel／Join／列序可攜契約測試通過；完整隔離後端 1980 passed、135 skipped、1 warning（52.87 秒）。
以上是合成證據與控制資料回歸，沒有真實 Hop／Vertica 重播，不計為 E2E。

下一步：release_replay_worker 加入 stage_json_source、雙檔執行前後核對、JSON launcher 參數及真實 log receipt，再補 orchestration 正反例與原生 HWF 重播；不可沿用目前 CSV 預設 staging 分支。完成後才進行新案例正式全鏈驗收。
本輪未重跑既有 Task。人工基準仍未量測，第 5–7 階段未完成，knowledge-workspace 尚未持久化。
