/**
 * 用户自备 DeepSeek API Key（BYOK）的本地存储助手
 *
 * Key 只存前端 localStorage（15 天 TTL），不传服务器存储；过期读取时自动清除。
 * 键名：fitcream.deepseek-api-key + fitcream.deepseek-api-key-ts（写入时间戳）。
 */
const DS_KEY_STORAGE = "fitcream.deepseek-api-key";
const DS_KEY_TS_STORAGE = "fitcream.deepseek-api-key-ts";
const DS_KEY_TTL_MS = 15 * 24 * 60 * 60 * 1000; // 15 天

/** 读取 key；过期/缺失返回 null（读取时顺带清理过期项） */
export function getDsKey(): string | null {
  try {
    const key = localStorage.getItem(DS_KEY_STORAGE);
    if (!key) return null;
    const ts = Number(localStorage.getItem(DS_KEY_TS_STORAGE) || 0);
    if (!ts || Date.now() - ts > DS_KEY_TTL_MS) {
      clearDsKey();
      return null;
    }
    return key;
  } catch {
    return null;
  }
}

/** 保存 key 并刷新时间戳 */
export function saveDsKey(key: string): void {
  try {
    localStorage.setItem(DS_KEY_STORAGE, key.trim());
    localStorage.setItem(DS_KEY_TS_STORAGE, String(Date.now()));
  } catch {
    // 存储不可用（隐私模式等）时静默忽略
  }
}

/** 清除 key（含过期清理与「key 无效」回退后清理） */
export function clearDsKey(): void {
  try {
    localStorage.removeItem(DS_KEY_STORAGE);
    localStorage.removeItem(DS_KEY_TS_STORAGE);
  } catch {
    // 忽略
  }
}

/** 当前 key 的过期时间戳（毫秒）；无 key 返回 null */
export function getDsKeyExpiry(): number | null {
  try {
    const ts = Number(localStorage.getItem(DS_KEY_TS_STORAGE) || 0);
    return ts ? ts + DS_KEY_TTL_MS : null;
  } catch {
    return null;
  }
}
