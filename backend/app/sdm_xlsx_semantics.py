"""Exact cell-content check for the current SDM candidate layout, not release QA."""
from decimal import Decimal, InvalidOperation
from io import BytesIO
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile
from .sdm_specification import build_sdm_candidate
from .sdm_xlsx_structure import inspect_sdm_xlsx, NS


def expected_sdm_cells(payload, run, naming, *, release_binding=None):
    candidate=build_sdm_candidate(payload,run,naming);d=candidate['document']
    labels={'DIRECT':'直接對應','GROUP_KEY':'分組欄位','SUM':'加總','COUNT_ROWS':'計算資料筆數','COUNT_NON_NULL':'計算非空值筆數','SOURCE_ORDINAL':'系統產生來源序號'}
    rows=[]
    for m in d['mappings']:
        sources=m['source_columns']
        rows.append([m['position'],m['target_column'],m['target_type'],labels[m['operation']],
            '、'.join((s['source_ref'] + '.' if d['version'] == 2 else '') + s['original_name'] for s in sources),
            '、'.join(s['stream_name'] for s in sources) if sources else
            '依 CSV 邏輯資料列位置從 1 產生，非 CSV 原始欄位' if m['operation']=='SOURCE_ORDINAL' else '整筆資料計數，無單一來源欄位'])
    rules=[['來源識別','、'.join(d['source_refs']) if d['version'] == 2 else d['source_ref']],['目標表',f'{d["target"]["schema"]}.{d["target"]["table"]}'],
        ['寫入模式','APPEND（附加資料）'],['篩選邏輯','ALL（全部成立）；EXCLUDE_UNKNOWN（排除比較結果未知的資料）']]
    if d['version']==3:
        order=d['source_order']
        rules.extend([
            ['來源序號',order['ordinal_column']+'（BIGINT，不可為 NULL）'],
            ['序號規則','CSV 邏輯資料列位置，從 1 連續遞增；標頭不計入，含換行的引號欄位仍為同一筆資料'],
            ['結果排序',order['ordinal_column']+' ASC；查詢須明確 ORDER BY，資料表實體儲存順序不構成保證'],
            ['答案比對','EXACT_SOURCE_SEQUENCE：逐列比對內容及序號，不忽略列序，不依業務鍵重新排序']])
    if d['version']==4:
        policy=d['excel_input_contract'];reference=d['excel_source']
        rules.extend([
            ['來源格式','XLSX；Apache Hop ExcelInput（POI）'],
            ['Excel 工作表',policy['worksheet']],
            ['Excel 標頭列',str(policy['header_row'])+'（從 1 起算；資料自下一列開始）'],
            ['空白列政策','SKIP（略過全空白資料列）' if policy['blank_rows']=='SKIP' else 'PRESERVE（保留全空白資料列）'],
            ['缺少儲存格','NULL（不補造資料）'],
            ['額外欄位','REJECT（拒絕非空的額外欄位）'],
            ['公式政策','REJECT（拒絕公式，不使用快取結果）'],
            ['文字空白','NONE（不自動去除前後空白）'],
            ['型別與錯誤','依 Naming Contract 型別驗證；FAIL（遇到轉換錯誤即停止，不略過錯誤資料列）'],
            ['Excel 來源 SHA-256',reference['content_checksum']],
            ['Excel Profile SHA-256',reference['profile_checksum']],
            ['Excel 讀取契約 SHA-256',reference['contract_checksum']]])
    for join in d.get('joins', []):
        prefix = 'Join ' + join['id']
        rules.extend([[prefix, f'{join["left_source"]} {join["join_type"]} JOIN {join["right_source"]}'],
                      [prefix + ' null 鍵', join['null_key_policy']],
                      [prefix + ' 重複鍵', join['duplicate_key_policy']],
                      [prefix + ' 字串比較', join['string_comparison']]])
        for i,key in enumerate(join['keys'],1):
            rules.append([f'{prefix} 鍵 {i}', f'{join["left_source"]}.{key["left_column"]} = {join["right_source"]}.{key["right_column"]}'])
    for i,f in enumerate(d['filters'],1):
        value=f'{f["column"]} {f["operator"]}'
        if f['constant']:
            v=f['constant']['value']
            v='空字串' if v=='' else str(v).lower() if isinstance(v,bool) else str(v)
            value+=f' {v} ({f["constant"]["type"]})'
        rules.append([f'條件 {i}',value])
    if not d['filters']:rules.append(['篩選條件','無篩選，保留全部來源資料'])
    rules.extend([['分組欄位',('、'.join(d['aggregation']['group_by']) or '無分組欄位（整體聚合）') if d['aggregation'] else '不聚合'],
        ['Run ID',d['run_id']],['Naming 版本',str(d['naming']['version'])],['Naming ID',d['naming']['contract_id']],
        ['Naming SHA-256',d['naming']['checksum']],['Specification SHA-256',d['specification_checksum']],['SDM SHA-256',candidate['checksum']]])
    result=[]
    if release_binding is not None:
        from .release_contract import document_binding
        binding=document_binding(release_binding,d['run_id'],d['specification_checksum'])
        rules.extend([['QA 核准 SHA-256',binding['qa_binding_checksum']],
            ['來源 SDM SHA-256',binding['source_sdm_checksum']],
            ['可攜驗證 SHA-256',binding['portability_checksum']]])
    for title,warning,header,body in [
        ('SDM 欄位對照','候選文件：未完成 QA，尚不可交付',['順序','輸出欄位','目標型別','轉換方式','來源原名','來源英文欄位'],rows),
        ('SDM 規則及版本','候選文件：不含執行證據或核准結果',['項目','已確認規格內容'],rules)]:
        cells={'A2':title,'A3':warning if release_binding is None else '交付版：QA 與可攜驗證指紋見規則頁；正式核准以 Release manifest 為準'}
        for row,values in enumerate([header,*body],5):
            for col,value in enumerate(values):
                if value!='':cells[f'{chr(65+col)}{row}']=value
        result.append(cells)
    return result


def _read_cells(content):
    with ZipFile(BytesIO(content)) as archive:
        shared=ET.fromstring(archive.read('xl/sharedStrings.xml'))
        if shared.tag!=f'{{{NS}}}sst' or any(n.tag!=f'{{{NS}}}si' for n in shared):
            raise ValueError('SDM_XLSX_SHARED_STRINGS')
        strings=[''.join(n.itertext()) for n in shared.findall(f'{{{NS}}}si')]
        used_strings=set()
        result=[]
        for name,maxcol in [('sheet1.xml','F'),('sheet2.xml','B')]:
            root=ET.fromstring(archive.read('xl/worksheets/'+name));cells={};seen=set()
            containers=root.findall(f'{{{NS}}}sheetData')
            if len(containers)!=1:
                raise ValueError('SDM_XLSX_CELL_STRUCTURE')
            rows=list(containers[0]);row_ids=set();selected=[]
            for row in rows:
                row_id=row.get('r','')
                if row.tag!=f'{{{NS}}}row' or re.fullmatch(r'[1-9][0-9]{0,2}|1000',row_id) is None or row_id in row_ids:
                    raise ValueError('SDM_XLSX_ROW_STRUCTURE')
                row_ids.add(row_id)
                for cell in row:
                    if cell.tag!=f'{{{NS}}}c' or re.sub(r'^[A-Z]+','',cell.get('r',''))!=row_id:
                        raise ValueError('SDM_XLSX_ROW_STRUCTURE')
                    selected.append(cell)
            if len(selected)!=sum(1 for n in root.iter() if n.tag.rsplit('}',1)[-1]=='c'):
                raise ValueError('SDM_XLSX_ORPHAN_CELL')
            for cell in selected:
                ref=cell.get('r','')
                match=re.fullmatch(r'([A-Z]+)([1-9][0-9]{0,3})',ref)
                if not match or len(match[1])!=1 or match[1]>maxcol or int(match[2])>1000 or ref in seen:
                    raise ValueError('SDM_XLSX_CELL_RANGE')
                seen.add(ref);kind=cell.get('t','n');raw=cell.findtext(f'{{{NS}}}v')
                if kind=='s':
                    if raw is None or not raw.isdecimal() or int(raw)>=len(strings):raise ValueError('SDM_XLSX_STRING_INDEX')
                    used_strings.add(int(raw))
                    value=strings[int(raw)]
                elif kind=='inlineStr':
                    value=''.join(n.text or '' for n in cell.findall(f'{{{NS}}}is//{{{NS}}}t'))
                elif kind=='str':
                    # The preceding structure gate rejects all formula nodes.
                    value=raw or ''
                elif kind=='n':
                    if raw is None:continue
                    try:value=Decimal(raw)
                    except InvalidOperation:raise ValueError('SDM_XLSX_NUMBER') from None
                    if not value.is_finite():raise ValueError('SDM_XLSX_NUMBER')
                else:raise ValueError('SDM_XLSX_CELL_TYPE')
                if value!='':cells[ref]=value
            result.append(cells)
        if used_strings!=set(range(len(strings))):
            raise ValueError('SDM_XLSX_UNUSED_STRINGS')
        return result


def validate_sdm_xlsx(content,payload,run,naming,*,release_binding=None):
    evidence=inspect_sdm_xlsx(content)
    expected=expected_sdm_cells(payload,run,naming,release_binding=release_binding)
    if _read_cells(content)!=expected:
        raise ValueError('SDM_XLSX_SPECIFICATION_MISMATCH')
    return {**evidence,'semantic_equality':'RELEASE_LAYOUT_MATCHED' if release_binding else 'CANDIDATE_LAYOUT_MATCHED',
            'status':'SDM_CONTENT_CHECKED_APPROVAL_EXTERNAL' if release_binding else 'SDM_CANDIDATE_CHECKED_NOT_RELEASED'}
