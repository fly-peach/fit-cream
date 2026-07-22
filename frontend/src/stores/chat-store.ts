import { create } from "zustand";

interface ChatState {
  currentThreadId: string | null;
  setThreadId: (id: string | null) => void;
  sidebarOpen: boolean;
  toggleSidebar: () => void;
}

export const useChatStore = create<ChatState>((set) => ({
  currentThreadId: null,
  setThreadId: (id) => set({ currentThreadId: id }),
  sidebarOpen: true,
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
}));