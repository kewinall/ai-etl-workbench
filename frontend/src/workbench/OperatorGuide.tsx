export function OperatorGuide({navigate}:{navigate:(path:string)=>void}) {
  return <article className="wb-project-content" aria-label="Pilot 操作指南">
    <section className="panel"><h2>從專案開始的 ETL 工程工作台</h2>
      <p>本機單一 Operator、多專案的內部 Pilot。PostgreSQL 保存平台控制資料；Vertica 是 ETL 測試來源與目標；Apache Hop 是唯一 ETL 執行引擎。</p>
      <p>可管理專案、設定、需求與版本，查閱 Hop、Vertica 比對、QA 與正式 Release 證據。個別案例交付需依該版本的即時核對結果；輸入核准或 Task 成功狀態不等於交付核准，也不代表整个平台驗收完成。</p>
      <div className="wb-actions"><button onClick={()=>navigate('/projects')}>選擇專案開始操作</button><button onClick={()=>navigate('/system')}>開啟平台設定中心</button></div>
    </section>
    <section className="panel"><h3>1. 設定工作範圍</h3>
      <ol><li>在專案工作區新增或選擇專案；第一頁「設定」維護名稱、說明、預設 AI／資料連線及中英命名字典。</li>
        <li>設定解析依序為 Task 明確選擇 → 專案預設 → 平台預設。沒有有效設定時停止，不隱含使用開發機連線。</li>
        <li>第二頁「歷史 Task」可搜尋與篩選最新 Run 狀態。點選 Task 查看完整內容；「建立 Task」前往獨立建立畫面。</li>
        <li>第三頁「Pilot 評估」保留全部 Run，包括失敗與取消；點選證據入口會選中該 Run，不使用最新成功版本代替。</li></ol>
      <p>修改後請儲存並確認結果。離開未儲存表單前會提醒；儲存失敗保留輸入，請先查看原因。</p>
    </section>
    <section className="panel"><h3>2. 設定 AI、連線與執行環境</h3>
      <ul><li>AI 供應商與模型：編輯 Profile、區域及角色路由；儲存設定不會自動呼叫模型。實際測試須明確授權並可能消耗額度。</li>
        <li>資料連線與目標：設定 Vertica 與明確 TLS 模式。保存後可做 SELECT 1 連線測試；不代表寫入或 ETL 已驗收。平台 PostgreSQL 屬部署設定，頁面僅顯示就緒狀態與變更指引。</li>
        <li>執行環境與路徑：指定 Worker 可存取的 Hop 與工作目錄；Windows 路徑不代表容器內存在相同檔案。</li>
        <li>機密與部署安全：連線機密僅可寫入；勿貼到需求、對話或一般設定欄位。加密主金鑰由部署環境提供。</li></ul>
      <p>本機 Copilot 使用 Windows 登入的獨立 Worker；容器不會自動借用該登入。每次真實驗收須依當次授權，不能沿用已消耗的一次性同意。</p>
    </section>
    <section className="panel"><h3>3. 準備需求與確認版本</h3>
      <ol><li>建立 Task 時輸入來源、目標與需求。成功上傳只是取得檔案及樣本資訊，不代表資料可執行。</li>
        <li>Task「需求與規格」建立準備版本，核對輸入與設定快照，再確認此版輸入。</li>
        <li>缺少寫入模式、日期期間等條件時，依需求檢查結果補正並建立新版；舊版保留，新版需要重新確認。</li>
        <li>可換檔的單一 CSV 版本：上傳新檔、檢視欄位、勾選換檔確認，再保存補正。取消換檔保留原來源。</li>
        <li>規格需保存、檢查與人工核准。上游異動後不可沿用舊核准執行。</li></ol>
      <p>在需求補正表單逐欄位新增「結構化轉換意圖」：來源欄位以 source.0／source.1 區分，明定篩選比較、常數型別、分組、COUNT_ROWS 或 COUNT_NON_NULL 及輸出順序。保存後重新確認新版；聚合指標另在命名契約確認 $metric.指標識別 的英文名稱與型別。</p>
      <p>規格保存被語意驗證拒絕時，可在協作紀錄查看節點及預期／實際差異。查閱或編譯預覽不會新增保存失敗事件；沒有意圖契約的舊版本仍需人工逐項核對。</p>
      <p>CHECKED／PIPELINE_NOT_READY 表示初步檢查完成但後續流程尚未接通，不是 ETL 成功。MATCH 只表示特定標準答案比對相符，不是 QA 或 Release 核准。</p>
    </section>
    <section className="panel"><h3>4. 查閱歷史與處理失敗</h3>
      <p>Task 六頁籤：概覽、需求與規格、協作紀錄、產物與流程、執行與 QA、交付。節點、原始設定、Hop／SQL 及既有下載保留；歷史產物不等同新版核准交付。</p>
      <p>看到 HOP_RESULT_UNKNOWN 時，先人工核對是否已寫入；不可直接重跑。NEEDS_REVIEW 需要查看具體阻擋原因，不能視為已完成。</p>
      <p>交付頁分別顯示 QA 關聯 SDM、候選包、隔離可攜驗證與正式交付核准。只有目前證據核對通過的正式 Release 才提供下載；歷史交付數量不保證目前核准有效。</p>
    </section>
    <section className="panel"><h3>驗收與使用邊界</h3>
      <p>真實模型與 Vertica 驗收需要可用設定及明確測試範圍。測試收集器、模型 mock、單元測試或單獨網站成功，不可替代完整 ETL 驗收。</p>
      <p>範例表重建須同時符合 ai_sample、平台登錄及同一專案；不得刪除業務表。停用的執行或交付入口不是故障，不應自行繞過。</p>
      <p>四情境 Pilot 與後續 20 案例、人工基準及成效報告仍待完成；不展示未實測的成功率或工時改善。</p>
    </section>
  </article>;
}
