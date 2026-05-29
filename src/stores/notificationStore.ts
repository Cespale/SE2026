import { create } from 'zustand';
import {
  NotificationItem,
  UnreadCount,
  listNotifications,
  getUnreadCount,
  markNotificationRead,
  markAllRead,
} from '../api/notification';

interface NotificationState {
  items: NotificationItem[];
  unread: UnreadCount;
  loading: boolean;
  pollTimer: number | null;

  startPolling: () => void;
  stopPolling: () => void;
  refreshUnread: () => Promise<void>;
  loadList: (notifType?: number, onlyUnread?: boolean) => Promise<void>;
  markOneRead: (id: string) => Promise<void>;
  markAllRead: (notifType?: number) => Promise<void>;
}

export const useNotificationStore = create<NotificationState>((set, get) => ({
  items: [],
  unread: { total: 0, chat: 0, notification: 0 },
  loading: false,
  pollTimer: null,

  startPolling: () => {
    const existing = get().pollTimer;
    if (existing) return;
    get().refreshUnread();
    const id = window.setInterval(() => {
      get().refreshUnread();
    }, 30_000);
    set({ pollTimer: id });
  },

  stopPolling: () => {
    const id = get().pollTimer;
    if (id) {
      window.clearInterval(id);
      set({ pollTimer: null });
    }
  },

  refreshUnread: async () => {
    try {
      const u = await getUnreadCount();
      set({ unread: u });
    } catch {
      // 未登录或网络问题忽略
    }
  },

  loadList: async (notifType, onlyUnread = false) => {
    set({ loading: true });
    try {
      const items = await listNotifications({ notifType, onlyUnread });
      set({ items });
    } finally {
      set({ loading: false });
    }
  },

  markOneRead: async (id) => {
    await markNotificationRead(id);
    set((s) => ({
      items: s.items.map((n) => (n.id === id ? { ...n, isRead: true } : n)),
    }));
    get().refreshUnread();
  },

  markAllRead: async (notifType) => {
    await markAllRead(notifType);
    set((s) => ({
      items: s.items.map((n) =>
        notifType === undefined || n.notifType === notifType
          ? { ...n, isRead: true }
          : n
      ),
    }));
    get().refreshUnread();
  },
}));
