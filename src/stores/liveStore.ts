import { create } from 'zustand';
import { apiRequest, API_BASE } from '../api';
import { useAuthStore } from './authStore';

export interface LiveRoom {
  id: string;
  title: string;
  categoryId: string;
  categoryName: string;
  cover: string;
  streamKey: string;
  pushUrl: string;
  pullUrl: string;
  anchorId: string;
  anchorName: string;
  anchorAvatar: string;
  onlineCount: number;
  startTime: string;
  endTime: string;
  status: number;
}

export interface ChatMessage {
  id: string;
  type: 'danmaku' | 'system' | 'online' | 'join' | 'leave';
  content: string;
  color?: string;
  position?: number;
  username?: string;
  userId?: string;
  count?: number;
  timestamp: string;
}

interface LiveState {
  rooms: LiveRoom[];
  currentRoom: LiveRoom | null;
  messages: ChatMessage[];
  onlineCount: number;
  ws: WebSocket | null;
  isConnected: boolean;
  isLoading: boolean;
  fetchRooms: (categoryId?: string) => Promise<void>;
  fetchRoomDetail: (roomId: string) => Promise<void>;
  createRoom: (title: string, categoryId: string, cover: string) => Promise<LiveRoom | null>;
  endRoom: (roomId: string) => Promise<void>;
  connectWebSocket: (roomId: string) => void;
  disconnectWebSocket: () => void;
  sendDanmaku: (content: string, color: string, position: number) => void;
  sendHeartbeat: () => void;
}

export const useLiveStore = create<LiveState>((set, get) => ({
  rooms: [],
  currentRoom: null,
  messages: [],
  onlineCount: 0,
  ws: null,
  isConnected: false,
  isLoading: false,

  fetchRooms: async (categoryId?: string) => {
    set({ isLoading: true });
    try {
      const query = categoryId && categoryId !== '0' ? `?category_id=${categoryId}` : '';
      const data = await apiRequest<{ items: LiveRoom[] }>(`/api/live/rooms${query}`);
      set({ rooms: data.items, isLoading: false });
    } catch (error) {
      console.error('获取直播间失败', error);
      set({ rooms: [], isLoading: false });
    }
  },

  fetchRoomDetail: async (roomId: string) => {
    set({ isLoading: true });
    try {
      const room = await apiRequest<LiveRoom>(`/api/live/rooms/${roomId}`);
      set({ currentRoom: room, onlineCount: room.onlineCount, isLoading: false });
    } catch (error) {
      console.error('获取直播间详情失败', error);
      set({ currentRoom: null, isLoading: false });
    }
  },

  createRoom: async (title: string, categoryId: string, cover: string) => {
    try {
      const room = await apiRequest<LiveRoom>('/api/live/rooms', {
        method: 'POST',
        body: JSON.stringify({ title, categoryId, cover })
      });
      set(state => ({ rooms: [room, ...state.rooms], currentRoom: room }));
      return room;
    } catch (error) {
      console.error('创建直播间失败', error);
      return null;
    }
  },

  endRoom: async (roomId: string) => {
    try {
      await apiRequest(`/api/live/rooms/${roomId}/end`, { method: 'POST' });
      set(state => ({
        rooms: state.rooms.map(r => r.id === roomId ? { ...r, status: 2, endTime: new Date().toISOString() } : r),
        currentRoom: null
      }));
    } catch (error) {
      console.error('结束直播失败', error);
    }
  },

  connectWebSocket: (roomId: string) => {
    const token = useAuthStore.getState().token || '';
    const wsBase = API_BASE.replace(/^http/, 'ws');
    const ws = new WebSocket(`${wsBase}/ws/live/${roomId}?token=${encodeURIComponent(token)}`);

    ws.onopen = () => {
      set({ isConnected: true });
      ws.send(JSON.stringify({ type: 'join' }));
      const heartbeat = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'heartbeat' }));
      }, 30000);
      (ws as any).heartbeatInterval = heartbeat;
    };

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === 'online') set({ onlineCount: msg.count });
      if (msg.type === 'join_ack') set({ onlineCount: msg.onlineCount });
      if (['danmaku', 'system'].includes(msg.type)) {
        set(state => ({
          messages: [...state.messages, {
            id: msg.id || Date.now().toString(),
            type: msg.type,
            content: msg.content,
            color: msg.color,
            position: msg.position,
            username: msg.username,
            userId: msg.userId,
            timestamp: msg.timestamp || new Date().toISOString()
          }]
        }));
      }
    };

    ws.onclose = () => {
      const interval = (ws as any).heartbeatInterval;
      if (interval) clearInterval(interval);

      if (get().ws === ws) {
        set({ isConnected: false, ws: null });
      }
    };

    set({ ws, messages: [] });
  },

  disconnectWebSocket: () => {
    const { ws } = get();
    if (ws) {
      const interval = (ws as any).heartbeatInterval;
      if (interval) clearInterval(interval);
      ws.close();
      set({ ws: null, isConnected: false, messages: [] });
    }
  },

  sendDanmaku: (content: string, color: string, position: number) => {
    const { ws } = get();
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'danmaku', content, color, position }));
    }
  },

  sendHeartbeat: () => {
    const { ws } = get();
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ type: 'heartbeat' }));
  }
}));
