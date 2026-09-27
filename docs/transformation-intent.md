# 結構化轉換意圖（第一個工程 checkpoint）

用途：把操作者確認的篩選、聚合、輸出需求與 Developer 規格分開保存，避免
「型別合法」被誤認為「符合需求」。不解析任意 SQL，也不從測試答案反推設計。

## 操作

在 Task「需求與規格」→「補正需求並建立新版」→「新增轉換意圖」，逐欄位設定：

- 篩選欄位、比較方式、型別與常數。條件固定 AND；一般 NULL 比較排除。
- 是否聚合、分組欄位、指標識別及函數。COUNT_ROWS 與 COUNT_NON_NULL 不可互換。
- 輸出欄位及順序。聚合輸出以 `$metric.<id>` 識別，另在命名契約確認型別及英文名。

原始欄位使用 `source.0.原名`／`source.1.原名`，由已確認 Naming Contract
解析英文名稱；同名左右欄位不混用。整數表單拒絕超過 JavaScript 可精確表示
範圍的值，不做靜默四捨五入。API 仍使用嚴格 64 位元整数驗證。

保存只建立待確認 revision，不執行 ETL；重新确认输入后才從 Gate 往下。
新意圖進入輸入 checksum 與 SA／Developer context，不沿用舊核准。省略欄位
表示保留既有契約，不是刪除保護；API 不提供移除已保存意圖的捷徑。

## 程式保護與證據

共用 validator 比對已解析意圖及設計，差異回覆
`SPEC_TRANSFORMATION_INTENT_MISMATCH`、`field_path`、`node_id`、
`requirement_path`、`expected`、`actual`。不產生 HPL，也不保存可核准規格。
契約不合法或命名缺少時停止，不由模型猜測補足。編輯器的空白權限探測不是
真實提案；只在探測排除意圖差異，實際驗證／編譯／保存仍強制比較。

已驗證：隔離 PostgreSQL API 拒絕門檻／聚合植錯，且無規格保存或寫入；
revision 冪等、舊快照保留、新版未核准；中文欄位與雙來源限定命名。
真實隔離網站逐欄位操作、API 保存後重讀、頁面重載及 390px 窄版面通過。

## 限制與下一步

已部署 QA 證據交接與攔截紀錄更新；本 checkpoint 不增加正式 20 案通過數。舊版本未具備
意圖契約時保持既有行為並顯示限制，不宣稱全面語意驗證。QA v9／v10 context
保存原始意圖，按已核對執行指紋的 compiler plan 解析來源及 metric 對照；
不使用模型提案或標準答案反推需求。Developer 必須引用 transformation.conditions，
QA prompt v8 說明證據界線。舊 context 不回寫，新意圖必須建立 revision。
新建 Task 畫面提供進入意圖補正的操作導引，尚非直接於建立表單填寫完整意圖。
API／Worker 已同版建置；仍須正式五項語意植錯與補正後交付，不能以測試替代。

對目前已確認且未寫入的版本，POST 規格保存被語意比對拒絕時會記錄
SPECIFICATION_SEMANTIC_REJECTED，包含輸入／設定／提案指紋及差異；相同
拒絕提交冪等，沒有可核准規格或執行授權。GET／驗證與編譯預覽維持唯讀。
協作紀錄顯示此事件與差異；保留紀錄不等於修正版本已通過。
已交付版本不修改、不重播。Workspace 同步仍待完成。
