# 部署用 SDM renderer 初次驗收

使用者已同意使用既有 openpyxl。新增 app.sdm_renderer.render_sdm_xlsx；正式部署不依賴 Codex artifact tool。後者只用於開發環境獨立開啟及視覺驗證。

## 已實作

- 使用既有 expected_sdm_cells 共用內容契約，依規格產生欄位對照及規則／版本兩頁。
- 名稱即使以 =、+、-、@ 開頭仍明確寫為字串，不產生公式。
- 僅整理本函式自行產生的 OOXML：移除文件作者／時間 metadata 與空 definedNames，固定 ZIP 順序及日期，保留九個白名單部件。沒有改寫／放寬外部 XLSX 驗證器。
- 輸出必須通過既有結構及逐格內容檢查，維持 qa_passed=false、release_ready=false。

## 實測

- renderer、structure、semantics、delivery_compiler 合併測試 51 passed（0.46 秒）。包括輸入不變、bytes 可重現、公式樣式原名安全回讀與過期規格拒絕。
- openpyxl 重新開啟成功，欄位型別、數字順序、Run ID 及 freeze panes 均核對。
- 獨立 artifact tool 首次開啟失敗：OPC Content Types 使用帶前綴的命名空間有相容問題。改為根節點預設 namespace，並重跑 51 項測試後獨立開啟成功。未將第一次失敗當成成功。
- 兩頁 PNG 已實際檢視，中文、型別、對照與版本 checksum 沒有裁切；公式檢查無公式。並未啟動 Microsoft Excel 原生應用。
- 合成候選 outputs/sdm-native-20260913-01/SDM-candidate.xlsx 的 SHA256：c0d68c8bd03dae52099fff4fb097fe876202bfd8d0df574e40bf27782112f076。

## 未完成

仍需 API／網站下载入口、不可變 artifact metadata 與核准版本綁定、較大規格與長文字版面驗收。此模組尚未部署。工作簿仍是候選文件，不是可交付 Release；Vertica 連線目標確認及完整 P1–P3 仍未完成。
