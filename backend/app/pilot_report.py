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
        parts.append('<h3>操作時間覆蓋</h3>')
        effort = cohort.get('effort') or {}
        if effort.get('status') == 'RECORDED_INTERVALS_ONLY':
            parts.append('<p>僅為已記錄區間，不是完整案例工時；真人來源為自行聲明，未驗證身分，不能推算改善率。</p>')
            for mode, label in [('WORKBENCH', '工作台操作'), ('MANUAL_BASELINE', '人工基準')]:
                item = effort['modes'][mode]
                seconds = '尚未量測' if item['recorded_seconds'] is None else f'已記錄 {e(item["recorded_seconds"])} 秒'
                parts.append(f'<p>{label}：{seconds}；有區間紀錄 {e(item["cases_with_recorded_intervals"])} / 20 案，未記錄 {e(item["cases_without_recorded_intervals"])} 案。</p>')
            parts.append(f'<p>排除代理／功能測試 {e(effort["excluded_nonhuman_sessions"])} 段，放棄 {e(effort["abandoned_sessions"])} 段；未結束區間：{"有，不計入小計" if effort["has_open_session"] else "無"}。</p>')
        else:
            parts.append('<p>計時覆蓋暫時無法核對，不代表零工時。</p>')
        parts.append('<h3>模型用量覆蓋（含所有版本）</h3>')
        usage = cohort.get('usage')
        if usage is None:
            parts.append('<p>用量覆蓋尚無資料，不推定為零消耗。</p>')
        else:
            parts.append('<ul>' + ''.join(f'<li>{e(item)}</li>' for item in usage['limitations']) + '</ul>')
            if not usage['groups']:
                parts.append('<p>尚無模型用量紀錄，不推定為零消耗。</p>')
            for group in usage['groups']:
                parts.append(f'<h4>{e(group["provider"])} / {e(group["model"])}</h4><p>紀錄 {e(group["journal_invocations"])} 筆；非已接受結果 {e(group["nonaccepted_invocations"])} 筆；供應商部分回報 {e(group["provider_partial_records"])} 筆。</p>')
                for key, label in [('input_tokens','輸入 Token'), ('output_tokens','輸出 Token'), ('total_tokens','總 Token'), ('ai_credits','AI credits'), ('premium_requests','Premium requests'), ('duration_ms','請求處理耗時（毫秒）')]:
                    item = group['metrics'][key]
                    amount = '未回報' if item['reported_sum'] is None else f'已回報合計 {e(item["reported_sum"])}'
                    complete = '完整總量不可用' if item['complete_sum'] is None else f'完整總量 {e(item["complete_sum"])}'
                    parts.append(f'<p>{label}：{amount}；覆蓋 {e(item["reported_invocations"])} / {e(group["journal_invocations"])} 筆，缺 {e(item["missing_invocations"])} 筆；{complete}。</p>')
        parts.append('<h3>逐案結果與證據索引</h3>')
        for row in cohort['cases']:
            evidence = row.get('scenario_evidence') or {}
            precondition = evidence.get('precondition') or {}
            treatment = {
                'SUCCESS': '正常流程，核對來源、固定答案及交付證據。',
                'REQUIREMENT_GAP': '檢查需求缺口是否先被阻擋，再於修訂後完成交付。',
                'SEMANTIC_DEFECT': '檢查預植語意差異是否在寫入前被攔截，並保留修訂證據。',
                'EXECUTION_RECOVERY': '檢查執行失敗、診斷及人工核對紀錄，再核對後續交付。',
            }.get(row['scenario'], '此情境尚無支援的處理摘要，不能推定已驗收。')
            parts.extend([
                f'<article><h3>{e(row["title"])}</h3>',
                f'<p>案例：{e(row["case_key"])} · 情境：{e(row["scenario"])}<br>交付狀態：{e(row["status"])} · 情境證據：{e((row.get("scenario_evidence") or {}).get("status"))}</p>',
                f'<p>驗收問題與處理要求：{e(treatment)}</p>',
                f'<p>核對結果：來源指紋{"已核對" if evidence.get("source_verified") is True else "未確認"}；固定答案{"已核對" if evidence.get("frozen_oracle_verified") is True else "未確認"}；前置情境{"有綁定證據" if precondition else "尚缺證據"}。</p>',
                f'<p>前置證據 Run：<code>{e(precondition.get("run_id"))}</code>；事件：<code>{e(precondition.get("event_id"))}</code>；類型：{e(precondition.get("kind"))}</p>',
                f'<p>準備版本 {e(row["attempt_count"])}；補正版本 {e(row["revision_count"])}。總經過時間：{e(row["elapsed_to_delivery_seconds"])} 秒（含等待，非人工工時）。</p>',
                f'<p>Task：<code>{e(row["task_id"])}</code><br>Run：<code>{e(row["run_id"])}</code><br>Release：<code>{e(row["release_id"])}</code><br>Release checksum：<code>{e(row["release_checksum"])}</code></p></article>'])
    parts.append('<p>本報告為核對區間內的唯讀結果，不是原子快照；詳細失敗歷史與執行證據請回平台查閱。使用瀏覽器列印功能可列印本頁。</p></main></html>')
    return ''.join(parts)
