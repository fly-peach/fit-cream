import { create } from "zustand";
import { persist } from "zustand/middleware";

interface ChatState {
  /** 当前选中的会话线程 id，持久化以便切换页面后返回上次对话 */
  currentThreadId: string | null;
  setThreadId: (id: string | null) => void;
  /** 右侧历史会话侧边栏是否展开 */
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
  toggleSidebar: () => void;
}

export const useChatStore = create<ChatState>()(
  persist(
    (set) => ({
      currentThreadId: null,
      setThreadId: (id) => set({ currentThreadId: id }),
      sidebarOpen: false,
      setSidebarOpen: (open) => set({ sidebarOpen: open }),
      toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
    }),
    {
      name: "fitcream-chat",
      // 仅持久化 currentThreadId，侧边栏展开状态不持久化
      partialize: (state) => ({ currentThreadId: state.currentThreadId }),
    }
  )
);