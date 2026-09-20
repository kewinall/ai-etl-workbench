# 規格一致的交付元件編譯

新增 delivery_compiler.py，重用 HWF／HPL 編譯與規格 validator，從同一份有效 Specification、Run、Naming 產生 DDL 候選。新函式不讀寫 DB、不修改舊 release.py、不開放 Release HTTP。

## 修正的缺口

舊 create_release 使用 Naming Contract 全部欄位建表，可能把僅來源使用的欄位納入目標。新 DDL 只依 output_columns 的順序及驗證後型別產生欄位，不加入未指定的鍵值、限制、DROP、TRUNCATE 或 IF NOT EXISTS。

新增 build_checked_bundle_candidate 重新編譯並逐位元組核對 HPL／HWF／DDL，然後才交給候選封裝核心核對集合與版本。僅聲稱相同 checksum 標籤不能通過；修改內容並重算其 checksum 仍被拒絕。

## 依據與驗證

- Vertica SQL 技能提供的 24.4.x 官方 PDF，第 3503 頁 CREATE TABLE / Create with column definitions。採明確 schema.table 與欄位型別格式。來源：https://docs.vertica.com/24.4.x/en/vertica_doc.pdf。
- 未連接 Vertica，實際版本／模式／拓樸未確認；此文件查證不代表其他版本或實際 DB 執行成功。
- test_delivery_compiler.py、test_release_bundle.py、test_hwf_compiler.py、test_release_http_gate.py：25 passed（0.39 秒）。
- 測試核對精確 DDL 文字、來源 amount 未被加入、編譯可重現、ZIP 中三項內容一致、三類篡改重算指紋拒絕，以及過期規格不產生 DDL。

## 尚未完成

SDM 與 PARAMETERS 的內容及來源仍未驗證，測試使用明確標示未驗證的記憶體位元組。候選輸出保持 NOT_VERIFIED／qa_passed=false／release_ready=false。尚須完成真實 Excel、可攜性檢查、權威核准解析、產物保存及真實 Vertica QA。首次核心驗收時尚未部署；後續預覽整合如下，仍未接入正式執行。P0–P3 目標未達成。

## DDL 預覽整合

同日 compile-preview 端點已接到 delivery compiler，網站新增「查看 DDL 候選（未執行）」及 DDL 指紋，保留 HPL/HWF 與既有規格操作。API、web、CONTROL Worker 已部署。

- 網站真實規格流程 1 passed（6.4 秒）：保存及核准規格後比較畫面與 API 的完整 DDL 文字、指紋、無執行授權／無 Release，以及展開 XML/DDL 後的 390px 窄版面。
- Task TASK-20260913-0215、Run 032a5ec9-8118-4475-a195-79e82a517d84、Specification bf50f688-f06b-4406-b73a-91aee38f88ac。
- PostgreSQL 規格 API 整合 7 passed（1.60 秒）：核對 DDL SHA-256 與只含輸出欄位，預覽不保存產物、不派發工作、上游失效不可通過。測試後 CONTROL Worker 已恢復。

此批沒有執行 DDL、Hop 或 Vertica，也没有追加模型呼叫。候選封裝核心仍未接入公開下載。
