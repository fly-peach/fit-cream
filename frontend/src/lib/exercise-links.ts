/**
 * 动作名 -> 站内详情链接
 *
 * 把 markdown 文本中出现的动作库动作名替换为 [/exercises/<id>] 链接，
 * 供计划提案（present_plan_tool content）等 AI 生成的文本里展示动作详情入口。
 *
 * - 全量动作名映射来自后端 /exercises/names（轻量 id/name/name_en），模块级缓存一次
 * - 跳过已有的 markdown 链接与行内代码，避免重复包链接
 * - 长名优先匹配，避免「深蹲」误命中「杠铃深蹲」等子串
 */
import { api } from "@/lib/api";

interface ExerciseNameEntry {
  id: string;
  name: string;
  name_en?: string | null;
}

let namesPromise: Promise<ExerciseNameEntry[]> | null = null;

function fetchNames(): Promise<ExerciseNameEntry[]> {
  if (!namesPromise) {
    namesPromise = api.get<ExerciseNameEntry[]>("/exercises/names").catch((err) => {
      namesPromise = null;
      throw err;
    });
  }
  return namesPromise;
}

/** 已有链接 [..](..) 或行内代码 `..`，原样保留不替换 */
const PROTECTED_RE = /(`[^`]*`|\[[^\]]*\]\([^)]*\))/g;

/**
 * 把 markdown 里的动作名替换为站内详情链接；映射加载失败或未命中时原样返回。
 */
export async function linkifyExerciseNames(markdown: string): Promise<string> {
  if (!markdown) return markdown;

  let entries: ExerciseNameEntry[];
  try {
    entries = await fetchNames();
  } catch {
    return markdown;
  }
  if (!entries.length) return markdown;

  const idByName = new Map<string, string>();
  for (const e of entries) {
    idByName.set(e.name, e.id);
    if (e.name_en) idByName.set(e.name_en, e.id);
  }

  // 首字符 -> 候选名列表（长名优先），按首字符索引避免逐位全量扫描
  const byFirst = new Map<string, string[]>();
  for (const name of idByName.keys()) {
    const c = name[0];
    if (!c) continue;
    const list = byFirst.get(c);
    if (list) {
      list.push(name);
    } else {
      byFirst.set(c, [name]);
    }
  }
  for (const list of byFirst.values()) {
    list.sort((a, b) => b.length - a.length);
  }

  // 收集受保护区间（已有链接/代码）
  const ranges: Array<{ start: number; end: number }> = [];
  let m: RegExpExecArray | null;
  PROTECTED_RE.lastIndex = 0;
  while ((m = PROTECTED_RE.exec(markdown))) {
    ranges.push({ start: m.index, end: m.index + m[0].length });
  }

  let result = "";
  let i = 0;
  const len = markdown.length;
  while (i < len) {
    const range = ranges.find((r) => r.start <= i && i < r.end);
    if (range) {
      result += markdown.slice(i, range.end);
      i = range.end;
      continue;
    }
    const candidates = byFirst.get(markdown[i]);
    let matched = false;
    if (candidates) {
      for (const name of candidates) {
        if (markdown.startsWith(name, i)) {
          result += `[${name}](/exercises/${idByName.get(name)})`;
          i += name.length;
          matched = true;
          break;
        }
      }
    }
    if (!matched) {
      result += markdown[i];
      i += 1;
    }
  }
  return result;
}
