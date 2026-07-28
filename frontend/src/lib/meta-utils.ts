/** 自定义记录项的一行（键 + 值），用列表而非对象，允许空键、保序、可多行 */
export interface MetaRow {
  key: string;
  value: string;
}

/** 后端 dict -> 行列表 */
export function toMetaRows(dict?: Record<string, unknown> | null): MetaRow[] {
  if (!dict) return [];
  return Object.entries(dict).map(([key, value]) => ({
    key,
    value: value == null ? "" : String(value),
  }));
}

/** 行列表 -> 后端 dict（丢弃空键行、键去空白） */
export function toMetaDict(rows: MetaRow[]): Record<string, string> {
  const out: Record<string, string> = {};
  for (const row of rows) {
    const k = row.key.trim();
    if (k) out[k] = row.value;
  }
  return out;
}
