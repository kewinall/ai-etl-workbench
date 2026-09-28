# JSON SDM 候選文件（2026-09-28）

工程進度，尚未部署正式或完成 JSON 交付驗收。

## 後續網站驗證

SdmPreview 已支援 V5；顯示端嚴格核對格式、固定政策、根結構與三個指紋，異常不顯示為已確認。
隔離 5195 實際上傳、補正、新版規格核准、SDM 預覽、候選保存與下載通過；Run 未開始寫入。
兩項顯示守門正反例亦通過：合計 3 passed（6.8 秒），其中僅一項是實際瀏覽器流程。
TypeScript／Vite 及 API／Web Docker build 通過，保留既有大 chunk 警告。
首次下載流程在保存時受阻，確認為隔離 Compose 缺少 WORKBENCH_ARTIFACT_ROOT；
新增專用 ui-test-artifacts 資料卷後重驗通過，不使用正式產物或密鑰。
XLSX 文件視覺驗收、JSON 可攜重播、正式真實全鏈仍未完成。以下保留前階段工程時點。

- SDM document V5 綁定 JSON 原始來源、Profile、讀取契約指紋；欄位對照沿用已驗證 Naming Contract 與規格。
- 規則頁明示 BOM 僅於副本移除、不重新序列化；缺鍵 NULL、拒絕額外／巢狀／重複鍵、保留空物件、固定 null launcher 選項與嚴格型別政策。
- 候選文件不宣稱執行、QA 或 Release 通過；不包含 upload ID 或樣本資料。
- 已核准規格 API 可讀取候選預覽；上游修改後舊核准失效，預覽仍拒絕。UI 尚未開放 V5 SDM，須後續接線並做真實網站回歸。

驗證：24 項針對性測試通過；隔離 PostgreSQL 完整回歸 1968 passed、135 skipped、1 warning（52.47 秒）。
首輪完整回歸因舊 API 測試仍預期功能未開放而失敗，已改成檢查新預覽內容與失效核准拒絕，重跑通過。
未做文件視覺驗收、真實模型／Hop／Vertica 或 ZIP 驗收；不得把以上測試算成全鏈交付。

下一步：接 SdmPreview V5 嚴格格式驗證與頁面，再擴充 release_portability、release_store、release_replay_worker 的 JSON 雙指紋與原生 HWF 重播；禁止 JSON 落入 CSV 預設分支。完成隔離回歸後才部署 API／Worker／Web 並建立新案例真實驗收。

人工基準依操作者決定保持未量測。第 5–7 階段未完成；knowledge-workspace 尚未持久化，本文件與專案索引作為接續依據。
