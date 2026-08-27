/**
 * Intake 信息采集表单卡片
 *
 * 把 present_form_tool 步骤渲染为可填写表单：
 * - 模板（字段/类型/选项）来自 form-templates.ts，agent 只传 form_id + 预填值
 * - agent 预填的字段（档案已有数据）渲染为只读，用户不可修改
 * - 缺失字段渲染为可编辑控件，提交后格式化为结构化用户消息发回对话，
 *   agent 读取后按 persist 分流：写入档案 / 仅本次参考
 */

import { useMemo, useState } from "react";
import { CheckCircle2Icon, ClipboardListIcon, LockIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { FORM_TEMPLATES, type FormFieldDef, type FormTemplate } from "@/components/form-templates";
import { cn } from "@/lib/utils";
import type { AgentStep } from "@/types/chat";

interface FormCardProps {
  step: AgentStep;
  /** 是否允许填写提交（仅最新一条助手消息且未在流式中） */
  interactive: boolean;
  onSubmit: (text: string) => void;
}

/** select 字段的值转展示文案 */
function optionLabel(field: FormFieldDef, value: unknown): string {
  const v = String(value);
  return field.options?.find((o) => o.value === v)?.label ?? v;
}

/** 预填值展示文本（数字带单位，select 转文案） */
function prefilledDisplay(field: FormFieldDef, value: unknown): string {
  if (field.type === "select") return optionLabel(field, value);
  const text = String(value);
  return field.unit ? `${text} ${field.unit}` : text;
}

/** 把提交时的原始值转为展示文案 */
function valueDisplay(field: FormFieldDef, raw: string): string {
  if (field.type === "select") return optionLabel(field, raw);
  return field.unit ? `${raw} ${field.unit}` : raw;
}

/** 构建提交消息：persist 模板提示写库，其余标注仅本次参考 */
function buildSubmitMessage(
  template: FormTemplate,
  filled: { field: FormFieldDef; raw: string }[],
  reused: { field: FormFieldDef; value: unknown }[]
): string {
  const lines: string[] = [`[表单提交: ${template.id}]`];
  if (template.persist) {
    lines.push("请调用 update_user_profile_tool 将以下新补充字段写入我的档案：");
  } else {
    lines.push("以下信息仅用于本次计划设计，请勿写入数据库：");
  }
  for (const { field, raw } of filled) {
    lines.push(`- ${field.label}: ${valueDisplay(field, raw)}`);
  }
  if (reused.length > 0 && template.persist) {
    const reusedText = reused
      .map(({ field, value }) => `${field.label} ${prefilledDisplay(field, value)}`)
      .join("、");
    lines.push(`（已复用档案中的字段：${reusedText}，无需重复写入）`);
  }
  return lines.join("\n");
}

export function FormCard({ step, interactive, onSubmit }: FormCardProps) {
  const input = (step.input || {}) as {
    form_id?: string;
    title?: string;
    description?: string;
    fields?: Record<string, unknown>;
  };
  const template = input.form_id ? FORM_TEMPLATES[input.form_id] : undefined;
  const prefilled = useMemo(() => {
    const raw = input.fields || {};
    const result: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(raw)) {
      if (v !== null && v !== undefined && v !== "") result[k] = v;
    }
    return result;
  }, [input.fields]);

  const [values, setValues] = useState<Record<string, string>>({});
  const [submitted, setSubmitted] = useState(false);

  if (!template) return null;

  const editableFields = template.fields.filter((f) => !(f.key in prefilled));
  const reusedFields = template.fields.filter((f) => f.key in prefilled);
  const missingRequired = editableFields.filter(
    (f) => f.required && !(values[f.key] || "").trim()
  );
  const canSubmit = interactive && !submitted && missingRequired.length === 0;

  const setValue = (key: string, v: string) =>
    setValues((prev) => ({ ...prev, [key]: v }));

  const handleSubmit = () => {
    if (!canSubmit) return;
    const filled = editableFields
      .filter((f) => (values[f.key] || "").trim())
      .map((f) => ({ field: f, raw: (values[f.key] || "").trim() }));
    const reused = reusedFields.map((f) => ({ field: f, value: prefilled[f.key] }));
    onSubmit(buildSubmitMessage(template, filled, reused));
    setSubmitted(true);
  };

  return (
    <div className="my-2 overflow-hidden rounded-xl border border-emerald-200 bg-white shadow-sm">
      <div className="flex items-start gap-2.5 border-b border-emerald-100 bg-emerald-50/40 px-4 py-3">
        <ClipboardListIcon className="mt-0.5 size-4 shrink-0 text-emerald-600" />
        <div className="min-w-0">
          <div className="text-sm font-semibold text-emerald-950">
            {input.title || template.title}
          </div>
          {input.description && (
            <div className="mt-0.5 text-xs text-emerald-700/70">{input.description}</div>
          )}
        </div>
        {submitted && (
          <span className="ml-auto inline-flex shrink-0 items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
            <CheckCircle2Icon className="size-3" />
            已提交
          </span>
        )}
      </div>

      <div className="space-y-3 px-4 py-3">
        {reusedFields.map((f) => (
          <div key={f.key} className="flex items-center justify-between gap-3 text-sm">
            <span className="shrink-0 text-muted-foreground">{f.label}</span>
            <span className="inline-flex items-center gap-1.5 font-medium text-emerald-900">
              {prefilledDisplay(f, prefilled[f.key])}
              <span className="inline-flex items-center gap-0.5 rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-normal text-emerald-600">
                <LockIcon className="size-2.5" />
                档案已有
              </span>
            </span>
          </div>
        ))}

        {editableFields.map((f) => {
          const locked = submitted || !interactive;
          const value = values[f.key] || "";
          return (
            <div key={f.key} className="space-y-1">
              <label className="text-xs font-medium text-emerald-900">
                {f.label}
                {f.required && <span className="ml-0.5 text-red-500">*</span>}
              </label>
              {f.hint && <p className="text-[11px] text-muted-foreground">{f.hint}</p>}
              {submitted ? (
                <div className="rounded-md bg-emerald-50/60 px-2.5 py-1.5 text-sm text-emerald-900">
                  {value ? valueDisplay(f, value) : "—"}
                </div>
              ) : f.type === "select" ? (
                <Select
                  value={value || undefined}
                  onValueChange={(v) => setValue(f.key, v)}
                  disabled={locked}
                >
                  <SelectTrigger className={cn("h-9 text-sm", !value && "text-muted-foreground")}>
                    <SelectValue placeholder="请选择">
                      {value ? optionLabel(f, value) : undefined}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    {(f.options || []).map((o) => (
                      <SelectItem key={o.value} value={o.value}>
                        {o.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              ) : f.type === "textarea" ? (
                <Textarea
                  value={value}
                  onChange={(e) => setValue(f.key, e.target.value)}
                  placeholder={f.placeholder}
                  rows={2}
                  disabled={locked}
                  className="text-sm"
                />
              ) : (
                <div className="relative">
                  <Input
                    type={f.type === "number" ? "number" : "text"}
                    value={value}
                    onChange={(e) => setValue(f.key, e.target.value)}
                    placeholder={f.placeholder}
                    disabled={locked}
                    className="h-9 text-sm"
                  />
                  {f.unit && (
                    <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">
                      {f.unit}
                    </span>
                  )}
                </div>
              )}
            </div>
          );
        })}

        {editableFields.length === 0 && (
          <p className="text-xs text-muted-foreground">所需信息档案中已完整，无需填写。</p>
        )}
      </div>

      {interactive && !submitted && editableFields.length > 0 && (
        <div className="flex items-center justify-between border-t border-emerald-100 px-4 py-2.5">
          <span className="text-[11px] text-muted-foreground">
            {template.persist
              ? "提交后这些基础数据将存入你的档案"
              : "提交后仅用于本次计划设计，不会保存"}
          </span>
          <Button
            size="sm"
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="bg-emerald-600 text-white hover:bg-emerald-700"
          >
            提交
          </Button>
        </div>
      )}
    </div>
  );
}
