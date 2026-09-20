# HWF 編譯與原生 Hop 驗收

新增 `hwf_compiler.py`：從同一份通過驗證的 Specification／Run／Naming 重新編譯 HPL，再建立 Start → Pipeline 的固定 HWF。等待子 Pipeline 完成、禁止逐筆執行、平行與重複排程，不新增任意 SQL、Shell 或自動重試。

HWF 宣告 SOURCE_CSV 並傳給子 Pipeline，引用同目錄 `pipeline.hpl`，符合候選 ZIP 的 `hop/workflow.hwf`／`hop/pipeline.hpl` 配置。description 記錄 HPL checksum；此描述不是 Hop 的執行時完整性驗證，Controller 仍須於派發前核對檔案指紋。

## 官方依據與原生修正

- Pipeline action 職責與參數下傳：[Apache Hop 官方說明](https://hop.apache.org/manual/latest/workflow/actions/pipeline.html)。
- XML 欄位依據本機 `apache/hop:2.12.0` 隨附的 samples/reflection/generate-fake-books.hwf；測試 local workflow metadata 依同映像隨附設定。
- 第一次原生測試 2 failed／2 passed：`Internal.Workflow.Filename.Directory` 無法解析，尚未進入 CSV 處理。
- 讀取同映像 hop-core-2.12.0.jar 的 Const.class，確認實際常數為 `Internal.Workflow.Filename.Folder`；修正後重跑通過。

## 本次驗證

`test_hwf_compiler.py` 與 `test_hwf_native.py`：4 passed（7.98 秒）。

- 2 項規則測試：重複編譯一致、固定動作／路徑／參數、SHA-256、無執行授權；無效規格不產生 HWF。
- 2 項原生測試：真正 hop-run 載入 HWF，呼叫同目錄 HPL，經 SOURCE_CSV 參數取得合成資料；使用含空格與逗號的掛載路徑。
- 成功案 exit 0，target.0 記錄 R=3、E=0。缺少 CSV 案 exit 非 0，source.0 記錄 ERROR，子 Pipeline 失敗能傳回工作流程。
- Docker `--network none`、固定映像且不 pull、測試資料唯讀掛載。

## 限制

原生測試將 HPL 的 TableOutput 改為 Dummy，只驗證 HWF 載入、相對路徑、參數、資料流及錯誤傳播。測試用修改後 HPL 不作為核准產物，HWF 中原 checksum 不代表修改後檔案已驗證。無 Vertica 連線或寫入、無模型呼叫；未驗證實際資料庫結果或 Release。

首次原生驗收時 HWF 編譯器僅為內部函式；後續網站整合如下。仍未接入正式 artifact 保存或 Release API，未啟用平台執行開關。P0–P3 完整驗收尚未完成。

## 後續 API／網站整合

同日將既有 compile-preview 端點改為回傳同次編譯的 HPL 與 HWF；原 validate／保存／核准端點不變。網站保留 HPL 檢視，新增 HWF XML、單次執行結構說明與兩份產物指紋。API、web 與 CONTROL Worker 已部署。

- 部署後真實規格網站流程：1 passed（11.0 秒）；確認 HWF 內相對路徑與指紋可見。Task TASK-20260913-0214、Run b1c25070-dcd8-470a-9aec-e41ab8f99e96、Specification 269b3fab-fab7-4cfc-8f12-2c396ca7a270。
- 隔離 PostgreSQL 規格 API 整合：7 passed（1.62 秒）。編譯回應中的 HPL／HWF SHA-256 正確，HWF 描述引用本次 HPL 指紋，重複預覽一致；Task/Run 狀態不變，未保存 specification／hop_artifact／agent_invocation。
- 測試後已恢復 CONTROL Worker。此批沒有模型呼叫或 Hop／Vertica 派發。

預覽不是已核准交付檔案，不提供 Release 下載，也不取代執行前指紋核對與真實 QA。
