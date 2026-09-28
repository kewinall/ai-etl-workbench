export function JsonSpecificationBinding({spec}: {spec: any}) {
  if (spec?.version !== 5) return null;
  return <section aria-label="JSON 規格來源綁定"><h5>JSON 來源與讀取版本</h5>
    <p>使用原生 JSON 讀取；來源檔案、欄位結構與讀取政策須與已確認版本一致。此規格確認不等於執行或交付核准。</p>
    <details><summary>查看 JSON 版本指紋</summary><dl>
      <dt>原始檔案</dt><dd className="spec-checksum">{spec.json_source.content_checksum}</dd>
      <dt>來源結構</dt><dd className="spec-checksum">{spec.json_source.profile_checksum}</dd>
      <dt>讀取政策</dt><dd className="spec-checksum">{spec.json_source.contract_checksum}</dd>
    </dl></details>
  </section>;
}
