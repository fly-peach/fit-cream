import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, Trash2 } from "lucide-react";
import { type MetaRow } from "@/lib/meta-utils";

interface MetadataEditorProps {
  value: MetaRow[];
  onChange: (value: MetaRow[]) => void;
  disabled?: boolean;
  /** 键输入框占位文案 */
  keyPlaceholder?: string;
  /** 值输入框占位文案 */
  valuePlaceholder?: string;
  /** 添加按钮文案 */
  addLabel?: string;
}

/**
 * 通用自定义记录项编辑器：行列表形式，用于动作 / 训练日 / 餐食的扩展数据。
 * 新增行为空键，由用户填写有意义的名称（如「训练时长」「目标心率」）。
 */
export function MetadataEditor({
  value,
  onChange,
  disabled,
  keyPlaceholder = "名称（如 训练时长 / 目标心率）",
  valuePlaceholder = "数值或说明",
  addLabel = "添加自定义项",
}: MetadataEditorProps) {
  const rows = value ?? [];

  const updateRow = (index: number, patch: Partial<MetaRow>) => {
    onChange(rows.map((r, i) => (i === index ? { ...r, ...patch } : r)));
  };

  const addRow = () => onChange([...rows, { key: "", value: "" }]);

  const removeRow = (index: number) => onChange(rows.filter((_, i) => i !== index));

  return (
    <div className="space-y-2">
      {rows.length === 0 && !disabled && (
        <p className="text-xs text-muted-foreground">暂无自定义项</p>
      )}
      {rows.map((row, index) => (
        <div key={index} className="flex items-center gap-2">
          <Input
            value={row.key}
            onChange={(e) => updateRow(index, { key: e.target.value })}
            disabled={disabled}
            placeholder={keyPlaceholder}
            className="h-8 flex-1 text-xs"
          />
          <span className="text-xs text-muted-foreground">:</span>
          <Input
            value={row.value}
            onChange={(e) => updateRow(index, { value: e.target.value })}
            disabled={disabled}
            placeholder={valuePlaceholder}
            className="h-8 flex-1 text-xs"
          />
          {!disabled && (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="size-7 shrink-0 text-red-400 hover:text-red-600"
              onClick={() => removeRow(index)}
            >
              <Trash2 className="size-3" />
            </Button>
          )}
        </div>
      ))}
      {!disabled && (
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="h-7 gap-1 text-xs"
          onClick={addRow}
        >
          <Plus className="size-3" />
          {addLabel}
        </Button>
      )}
    </div>
  );
}

/** 只读展示自定义记录项 */
export function MetadataPreview({ value }: { value: Record<string, unknown> | null | undefined }) {
  const entries = Object.entries(value || {});
  if (entries.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1.5">
      {entries.map(([k, v]) => (
        <span
          key={k}
          className="inline-flex items-center rounded-md bg-slate-100 px-2 py-0.5 text-[10px] text-slate-600"
        >
          {k}: {v == null ? "" : String(v)}
        </span>
      ))}
    </div>
  );
}
