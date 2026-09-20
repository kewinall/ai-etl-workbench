const outcomes: Record<string, {title: string; detail: string; next: string}> = {
  HOP_PREPARATION_INVALID: {
    title: '執行準備失敗，尚未啟動 Hop',
    detail: '領取授權後，來源檔案或 HPL 的完整性核對未通過。此次沒有啟動引擎；已領取的授權不會自動再次使用。',
    next: '請檢查來源與產物版本，保留此次紀錄。修正後須重新確認版本與執行授權；目前網站尚未提供此重跑流程。',
  },
  HOP_EXECUTED_QA_REQUIRED: {
    title: 'Hop 執行完成，仍待 QA 驗證',
    detail: '引擎回報完成，不代表資料結果正確，也不代表可交付。',
    next: '仍須比對目標筆數、標準答案、規格與產物一致性，通過後才能進入人工交付核准。',
  },
  HOP_EXECUTION_FAILED: {
    title: 'Hop 回報執行失敗，請先核對寫入範圍',
    detail: '失敗不代表所有寫入已回復；目標可能已有部分資料。平台不會自動重試。',
    next: '請保留 Hop Log、檢查目標資料，並至需求與規格的版本內容完成「人工核對與結案」。結案不會重跑或回復資料。',
  },
  HOP_RESULT_UNKNOWN: {
    title: 'Hop 執行結果未知，禁止直接重跑',
    detail: '此版本已進入外部寫入階段，但沒有可靠的最終結果；可能是 Worker 租約失效、執行器異常或回報無法驗證。目標可能已寫入部分或全部資料。',
    next: '請先保留 Hop Log，核對目標資料與本次執行範圍，再至需求與規格的版本內容完成「人工核對與結案」。平台不會自動重試，也不接受失效 Worker 的成功回報。',
  },
};

export function HopOutcome({code}: {code?: string}) {
  const outcome = code ? outcomes[code] : undefined;
  if (!outcome) return null;
  return <section role="alert" aria-label="執行結果待核對">
    <h4>{outcome.title}</h4><p>{outcome.detail}</p><p>{outcome.next}</p>
  </section>;
}
