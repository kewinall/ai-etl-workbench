# SDM XLSX 結構檢查

新增 sdm_xlsx_structure.py，並接到 build_checked_bundle_candidate 的 SDM 分支。只支援目前兩頁 renderer 的九個固定 ZIP 成員；拒絕未知／重複成員、巨集附加檔、symlink、加密成員、超量解壓、DTD/entity、公式、hyperlink、外部關係、OLE、definedName 與隱藏列／表標記。

全程記憶體檢查，不解壓至磁碟、不解析外部資源；UTF-8 XML 才接受。單一 XML 最大 4 MiB，總壓縮檔／解壓內容最大 16 MiB。這是受限 renderer 的結構檢查，不是通用 Excel 匯入器。

## 實測

- 結構分支 14 passed（0.04 秒）。測試主要為最小 XML container，非完整 Excel 檔案。
- 與 delivery compiler／bundle／HTTP Gate 合併：41 passed（0.39 秒），包含 SDM 加公式後重算 checksum 仍被封裝入口拒絕。
- 唯讀檢查實際產生的 outputs/sdm-render-20260913-01/SDM-candidate.xlsx：9 parts，STRUCTURE_CHECKED_NOT_RELEASED，SHA-256 cb52844ed01573550ec24bbca9d7192be9abd89c6437cc992d71244b75ba3955。
- 未改寫工作簿、未建立第二份文件，未呼叫模型或資料庫。

## 限制

目前不是完整 OOXML schema validator；不證明 Excel 一定能開啟任意通過容器，也未比對欄位值與 Specification／Naming。仍需校驗 SDM 語意、文字中的機密／主機資訊、實際 Excel 回讀與核准來源；workbook 必需關係集合已於後續補齊如下。

回傳 semantic_equality=NOT_VERIFIED、portability=NOT_VERIFIED、qa_passed=false、release_ready=false。新檢查尚未部署；候選封裝仍無公開下載入口。正式 P0–P3 驗收未完成。

## 後續關係完整性修正

先前只限制單一關係的目的地，空關係集合仍可能通過。現在要求 package 唯一 officeDocument 關係，以及 workbook 的 styles、theme、sharedStrings、兩張 worksheet 關係恰好完整，並核對 namespace／節點類型。

兩張工作表須有不同且有效的 sheetId，各自 r:id 必須對應固定 sheet1.xml／sheet2.xml；交換、重用、缺漏或無法解析的參照拒絕，worksheet 根節點也必須正確。

- 結構＋候選編譯封裝回歸：32 passed（0.27 秒）。新增 9 個缺漏、重複、孤立或錯接參照案例。
- 既有實際 SDM XLSX 再次通過，SHA-256 不變；唯讀檢查、未重新匯出。
- 不把關係完整視為內容語意或 Release 核准，亦未啟用正式入口。
