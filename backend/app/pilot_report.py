"""Printable, allowlisted rendering of the existing read-only measurement result."""
from html import escape


def render(data):
    """Do not serialize raw evidence, settings, logs, or source rows into exports."""
    def e(value):
        return escape('尚無資料' if value is None else str(value), quote=True)

    parts = ['<!doctype html><html lang="zh-Hant"><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width,initial-scale=1">',
             '<title>Pilot 成果與證據報告</title><style>',
             'body{font:16px/1.65 system-ui,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;color:#182638}',
             'article{border-top:1px solid #ccd5df;margin-top:1.5rem;padding-top:1rem;break-inside:avoid}',
             'code{overflow-wrap:anywhere}h1,h2,h3{line-height:1.3}li{margin:.4rem 0}',
             '@media print{body{max-width:none;margin:0;font-size:11pt}h2,h3{break-after:avoid}}',
             '</style><main><h1>Pilot 成果與證據報告</h1>',
             '<p>內部合成案例 Pilot；可交付不等於情境驗收通過，也不代表人工工時改善。</p>',
             f'<p>專案：<code>{e(data["project_id"])}</code><br>核對區間：{e(data["checked_from"])} ～ {e(data["checked_until"])}</p>',
             '<h2>摘要與判讀限制</h2><ul>']
    parts.extend(f'<li>{e(item)}</li>' for item in data['limitations'])
    parts.append('</ul>')
    if not data['cohorts']:
        parts.append('<p>尚無正式登錄集合，不計算通過率。</p>')
    for cohort in data['cohorts']:
        if cohort['denominator'] != 20 or len(cohort['cases']) != 20:
            raise ValueError('PILOT_REPORT_POPULATION_INVALID')
        parts.extend([
            f'<h2>{e(cohort["name"])}</h2>',
            f'<p>目前可交付 {e(cohort["release_ready_count"])} / 20；符合凍結情境證據 {e(cohort.get("scenario_evidence_matched_count"))} / 20。無法確認 {e(cohort["unverified_count"])} 案。</p>',
            '<p>首次通過率、完整人工工時、人工基準、改善率與成本：尚無完整量測。失敗與修訂未從分母移除。</p>',
            f'<p>集合：<code>{e(cohort["cohort_id"])}</code><br>凍結方案 checksum：<code>{e(cohort["plan_checksum"])}</code></p>'])
        for row in cohort['cases']:
            parts.extend([
                f'<article><h3>{e(row["title"])}</h3>',
                f'<p>案例：{e(row["case_key"])} · 情境：{e(row["scenario"])}<br>交付狀態：{e(row["status"])} · 情境證據：{e((row.get("scenario_evidence") or {}).get("status"))}</p>',
                f'<p>準備版本 {e(row["attempt_count"])}；補正版本 {e(row["revision_count"])}。總經過時間：{e(row["elapsed_to_delivery_seconds"])} 秒（含等待，非人工工時）。</p>',
                f'<p>Task：<code>{e(row["task_id"])}</code><br>Run：<code>{e(row["run_id"])}</code><br>Release：<code>{e(row["release_id"])}</code><br>Release checksum：<code>{e(row["release_checksum"])}</code></p></article>'])
    parts.append('<p>本報告為核對區間內的唯讀結果，不是原子快照；詳細失敗歷史與執行證據請回平台查閱。使用瀏覽器列印功能可列印本頁。</p></main></html>')
    return ''.join(parts)
