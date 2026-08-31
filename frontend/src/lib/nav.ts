/**
 * 详情页打开策略
 *
 * 桌面 Web（有鼠标指针）用浏览器新标签页打开详情；
 * 原生 App（Capacitor WebView）与触屏设备新标签页体验差/不可用，保持站内导航。
 * 判定口径与 chat.tsx 拍照按钮的 isMobile 一致。
 */
import { Capacitor } from "@capacitor/core";
import type { NavigateFunction } from "react-router-dom";

export function isDesktopWeb(): boolean {
  if (Capacitor.isNativePlatform()) return false;
  if (typeof window === "undefined") return false;
  return !window.matchMedia("(pointer: coarse)").matches;
}

export function openDetail(navigate: NavigateFunction, path: string): void {
  if (isDesktopWeb()) {
    window.open(path, "_blank", "noopener");
    return;
  }
  navigate(path);
}
