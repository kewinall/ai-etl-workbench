# JSON 讀取契約、原生來源片段與副本驗收（2026-09-28）

## 判定

已新增嚴格平面 JSON 讀取契約、確定性 Hop 來源產生器及受控暫存副本。
**尚未接入正式 Run／Naming／規格版本、QA／SDM／Release，沒有部署正式服務；
不能視為 JSON 完整 ETL 驗收或第 5 階段完成。** 原 Excel 及既有交付不重跑。

## 真實發現與修正

1. 原生檔案清單模式將 `doNotFailIfNoFile=N` 設為嚴格值時，Hop 2.12 的
   `prepareToRowProcessing()` 在 `InputsReader.iterator()` 建立清單之前檢查 `data.files`，
   有效檔案也會失敗。初次試驗調成 Y 可讀，但最終產生器**沒有採用放寬缺檔保護**。
2. `$[...]` 同時是 Hop 變數語法。JSONPath 改用等價的 `$.[*]["欄名"]`／`$.["欄名"]`，
   欄名中的 `$` 編碼為 Unicode escape，避免名稱被當成變數；中文、點、引號、反斜線、
   `${...}` 與 `$[...]` 字面欄名均以原生讀取比對。
3. 改為從檔名欄讀取後，`removeSourceField=Y` 的 `buildBaseOutputRow()` 會複製
   輸入 row buffer 的預留空間，單一輸出欄發生越界。最終改成保留該欄，再由明確
   `SelectValues` 僅保留規格欄位；單欄高精度數值及缺檔反例全部重新驗證。
4. Hop 2.12 直接讀取 UTF-8 BOM 文件不能正確取得 JSONPath。新增明示
   `bom_handling=REMOVE_UTF8_BOM`：只移除副本最前面三個 BOM bytes，保留其餘每一 byte。
   原上傳檔不改；證據同時保存原始／reader checksum、byte count 與 normalization。
   保留未處理 BOM 的原生失敗測試，不把它冒充直接支援。

原生來源片段：`RowGenerator（單一檔名參數）→ JsonInput → SelectValues（排除參數欄）`。
參數節點不產生業務資料；實際 JSON 解析仍由 Apache Hop 執行，不轉成 CSV 或 Python ETL。

## 契約與限制

- `JsonInputContractV1` 只接受精確整數 version、UTF-8（可有 BOM）、明確 OBJECT／ARRAY，
  缺 key 為 NULL、拒絕額外／巢狀／重複 key、不 trim、保留全 NULL 列、錯誤即停止。
- 完整 byte scan 綁定欄位集合及順序、root shape、原檔及政策指紋；
  proof 明確為 `JSON_STRUCTURE_VALIDATED_NOT_EXECUTABLE`，沒有 execution authority。
- 沿用 profile 的全檔限制；來源片段最多 200 欄。欄位英文名稱與型別由程式驗證；
  不接受任意 XML／JSONPath／工具呼叫，禁止碰撞內部檔名欄。
- `stage_json_source` 只讀取 managed upload 的指定 UUID／size／checksum；不以任意 path 回退。
  原檔變更被拒絕；attempt 只生成私有 reader 副本，finally 清除該副本而不刪原檔。
- 原生測試明確設定 `HOP_JSON_INPUT_INCLUDE_NULLS=Y`。正式 launcher／可攜環境接線時
  必須同樣固定並綁定此語意，不能依賴操作者電腦的隱含設定。
- 此次只證明列出的原生行為，尚未完成所有 DATE／TIMESTAMP、型別錯誤的寫入前拒絕、
  不同政策版本、正式 CLI／HWF 啟動參數或 Vertica 目的端驗收。

## 驗證方式

最終單元／原生／副本／來源發行組合 **44 passed（48.74 秒）**，其中 12 項為
明確啟用的無網路原生案例。最終隔離後端回歸 **1757 passed、123 skipped、1 warning
（39.53 秒，exit 0）**。123 項 skips 包含另行執行的 12 項 JSON 原生測試，以及其他
需外部服務／Windows／真實角色證據的 opt-in 測試，不把它們全部計為通過。

初期原生失敗保留在上述原因分析：曾出現檔案清單／JSONPath、測試參數欄的 XML key、
單欄 remove-source-field 索引及 BOM 解析問題。最終以真正產生器重新執行全部正反案例；
没有縮小數值斷言或用 mock 取代 Hop。測試用檔名欄正確 key 由安裝插件反射確認為 `nullif`。

- 使用固定已安裝 Hop 2.12，Worker 映像身份：
  `sha256:7b77c3c713555edca105139f53ad09ba887f8f0f54ec09b77a79a07e06cb5328`。
- 原生測試容器 `--network none`，候選／attempt 及驗證程式唯讀掛載，目的為 Dummy collector；
  沒有模型、DB、憑證或 Release 操作。
- 原生測試直接呼叫 `json_input_fragment`，沒有另外維護一份可通過的手寫 XML。
  固定參數經 Hop 變數替換，包含讀取已驗證 attempt 後原上傳改動也不重新開啟原檔的案例。
- 精度測試包含 JSON numeric token 的 26 位數值及 18 位小數、最大安全 BIGINT 邊界，
  並比較中文／前導零／空白／空字串／NULL／全 NULL 列／陣列順序。
- 缺檔、空檔、格式錯誤及未準備 BOM 必須以原生失敗結束。

## 接續

1. 將契約接入 managed profile 確認、Requirement Gate、Run revision 及網站欄位式確認；
   政策或來源改變必須使舊核准失效，保留歷史。
2. 補 typed full-file validation、新規格版本及來源節點清單，將原始與 reader 雙指紋接入
   reservation、launcher、runtime／QA、SDM、manifest 及可攜重播。
3. 真實新案例驗證模型→Hop→Vertica→QA→SDM→Release，才能宣稱此 JSON 流程完成。
   原 20 案分母不變；人工基準仍依指示未量測。

knowledge-workspace WS-0007 本輪讀取仍為舊狀態，**尚未持久化至 knowledge-workspace**；
接手者需同步本工程證據、Excel 真實交付與上述下一步，不複製上傳資料／私有身份。

## 官方對照

- [Hop 2.12 JSON Input 手冊](https://hop.apache.org/manual/2.12.0/pipeline/transforms/jsoninput.html)
- [2.12.0-rc1 對應 JsonInput 原始碼](https://github.com/apache/hop/blob/8f8960e861c4fe55ca849c0016bb10c6f78c9ccf/plugins/transforms/json/src/main/java/org/apache/hop/pipeline/transforms/jsoninput/JsonInput.java)
- [同版本 InputsReader](https://github.com/apache/hop/blob/8f8960e861c4fe55ca849c0016bb10c6f78c9ccf/plugins/transforms/json/src/main/java/org/apache/hop/pipeline/transforms/jsoninput/reader/InputsReader.java)

原始碼用於定位，實際驗收以已安裝映像的執行結果為準，沒有升級 Hop 或替換其依賴。
