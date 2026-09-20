export function PilotHome() {
  return <section className="panel wb-project-home" aria-label="Pilot 成果">
    <h2>Pilot 驗收與成果</h2>
    <p>目前尚無可供比較的完整 P0–P3 實測成果。初步檢查、單元測試及舊版 Task 成功紀錄不等於新版 Pilot 交付。</p>
    <ol><li>P0：可靠基礎與專案操作入口 — 進行中</li><li>P1：真實 CSV → Hop → Vertica → Release — 尚未通過</li><li>P2：四情境驗收與失敗恢復 — 尚未通過</li><li>P3：20 案例、人工基準與主管報告 — 尚未完成</li></ol>
    <p>模型用量紀錄與 Pilot 成效分開看待；沒有人工基準，不顯示改善率，也不提供未完成的報告匯出。</p>
  </section>;
}
