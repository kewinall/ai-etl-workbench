"""Conservative content screening; does not prove portability or authorize release."""
from io import BytesIO
from zipfile import ZipFile,BadZipFile
import re
from xml.etree import ElementTree as ET
from .release_bundle import BundleArtifact,MEMBERS,MAX_MEMBER_BYTES

# Fixed OOXML vocabulary is structure, not a deployment value. Values are never
# exempted, including values on these attributes. Unknown names remain screened.
_SHEET_NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
_STRUCTURAL_ATTRIBUTES=frozenset('''count name val type ref sqref r s t style
numFmtId fontId fillId borderId xfId applyAlignment applyBorder applyFill
applyFont applyNumberFormat applyProtection pivotButton quotePrefix
horizontal vertical textRotation wrapText shrinkToFit indent relativeIndent
justifyLastLine readingOrder locked hidden width height customWidth customHeight
min max bestFit outlineLevel collapsed ht spans dyDescent sheetId state
defaultRowHeight baseColWidth defaultColWidth tabSelected workbookViewId
showGridLines zoomScale zoomScaleNormal activeCell activePane topLeftCell
left right top bottom header footer orientation paperSize fitToHeight fitToWidth
rgb indexed theme tint auto patternType formatCode builtinId customBuiltin
outline diagonalUp diagonalDown diagonal vertical horizontal start end
fullCalcOnLoad calcId date1904 forceFullCalc fullPrecision codeName
showOutlineSymbols summaryBelow summaryRight syncHorizontal syncVertical
activeTab autoFilterDateGrouping defaultPivotStyle defaultTableStyle firstSheet
minimized showHorizontalScroll showSheetTabs showVerticalScroll tabRatio visibility
{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id
'''.split())


def _xml_content(part):
    if b'<!DOCTYPE' in part.upper() or b'<!ENTITY' in part.upper():
        raise ValueError('RELEASE_SCREEN_UNSUPPORTED_XML')
    try:
        root=ET.fromstring(part,parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True,insert_pis=True)))
    except ET.ParseError:
        raise ValueError('RELEASE_SCREEN_INVALID_SDM') from None
    chunks=[]
    for node in root.iter():
        if isinstance(node.tag,str):
            chunks.append(node.tag)
        for key,value in node.attrib.items():
            if not (isinstance(node.tag,str) and node.tag.startswith('{'+_SHEET_NS+'}') and key in _STRUCTURAL_ATTRIBUTES):
                chunks.append(key)
            chunks.append(value)
        chunks.extend((node.text or '',node.tail or ''))
    # Also inspect joined rich-text runs, so splitting a credential across XML
    # elements cannot evade screening. Comments and processing instructions stay.
    chunks.append(''.join(root.itertext()))
    return chunks


def check_release_content(artifacts,*,forbidden_values):
    if not isinstance(forbidden_values,(list,tuple)) or any(not isinstance(v,str) or not v for v in forbidden_values):
        raise ValueError('RELEASE_SCREEN_INPUT_INVALID')
    if len(artifacts)!=len(MEMBERS) or {a.kind for a in artifacts if isinstance(a,BundleArtifact)}!=set(MEMBERS):
        raise ValueError('RELEASE_SCREEN_ARTIFACTS_REQUIRED')
    for item in artifacts:
        if len(item.content)>MAX_MEMBER_BYTES:raise ValueError('RELEASE_SCREEN_TOO_LARGE')
        if item.kind=='SDM':
            try:
                with ZipFile(BytesIO(item.content)) as archive:
                    entries=archive.infolist()
                    if len(entries)>32 or sum(e.file_size for e in entries)>MAX_MEMBER_BYTES:
                        raise ValueError('RELEASE_SCREEN_TOO_LARGE')
                    if any(e.flag_bits&1 or not e.filename.endswith(('.xml','.rels')) for e in entries):
                        raise ValueError('RELEASE_SCREEN_UNSUPPORTED_SDM')
                    parts=[archive.read(e) for e in entries]
            except BadZipFile:raise ValueError('RELEASE_SCREEN_INVALID_SDM') from None
        else:parts=[item.content]
        for part in parts:
            try:text=part.decode('utf-8')
            except UnicodeDecodeError:raise ValueError('RELEASE_SCREEN_NON_TEXT') from None
            # Parse SDM XML so fixed schema attribute names are not credentials.
            # Every value, unknown name, comment and PI is still inspected.
            from html import unescape
            candidates=_xml_content(part) if item.kind=='SDM' else [text,unescape(text)]
            if any(value.casefold() in candidate.casefold() for value in forbidden_values for candidate in candidates):
                raise ValueError('RELEASE_DEPLOYMENT_VALUE_FOUND')
            normalized=unescape(text).casefold()
            if re.search(r'(?i)(?:(?<![a-z0-9])[a-z]:[\\/]|file://|\\\\[a-z0-9]|/(?:home|users|mnt|opt|app|tmp|var)/)',normalized):
                raise ValueError('RELEASE_ABSOLUTE_PATH_FOUND')
            if re.search(r'(?i)(?:localhost|host\.docker\.internal|\b127\.0\.0\.1\b|\b169\.254\.)',normalized):
                raise ValueError('RELEASE_HOST_REFERENCE_FOUND')
    return {'status':'CONTENT_SCREEN_PASSED','portability':'NOT_VERIFIED','release_ready':False}
