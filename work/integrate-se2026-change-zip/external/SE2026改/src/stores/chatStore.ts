import { create } from 'zustand';
import {
  ChatMessage,
  Conversation,
  buildChatWsUrl,
  listConversations,
  listMessages,
  markConversationRead,
  openConversation,
  recallMessage,
  sendMessageHttp,
} from '../api/chat';
import { useAuthStore } from './authStore';
import { useNotificationStore } from './notificationStore';

interface ChatState {
  ws: WebSocket | null;
  myUserId: string | null;
  conversations: Conversation[];
  messagesByConv: Record<string, ChatMessage[]>;
  activeConvId: string | null;
  typingPeers: Record<string, number>;  // peerId -> expire ts
  loadingMessages: boolean;

  connect: (token: string) => void;
  disconnect: () => void;

  loadConversations: () => Promise<void>;
  openConversationWith: (peerId: string) => Promise<Conversation>;
  selectConversation: (convId: string) => void;
  loadMessages: (convId: string) => Promise<void>;

  sendText: (peerId: string, content: string) => Promise<void>;
  sendTyping: (peerId: string) => void;
  recall: (msgId: string) => Promise<void>;
  markRead: (convId: string) => Promise<void>;
}

function sortByLatest(list: Conversation[]) {
  return [...list].sort((a, b) => {
    const ta = a.lastMessageAt ? new Date(a.lastMessageAt).getTime() : 0;
    const tb = b.lastMessageAt ? new Date(b.lastMessageAt).getTime() : 0;
    return tb - ta;
  });
}

// 把一条新消息写入 messagesByConv 并更新会话列表。
// WS 回显（onmessage 'message'）与 HTTP 兜底（sendText 的 else 分支）共用，
// 保证两条发送路径的行为一致。
type ChatSetState = (partial: ChatState | Partial<ChatState> | ((state: ChatState) => ChatState | Partial<ChatState>)) => void;

function appendIncomingMessage(set: ChatSetState, get: () => ChatState, m: ChatMessage) {
  const convId = m.conversationId;
  set((s) => {
    const list = s.messagesByConv[convId] || [];
    if (list.some((x) => x.id === m.id)) return s;
    const conv = s.conversations.find((c) => c.id === convId);
    let conversations = s.conversations;
    if (conv) {
      const isActive = s.activeConvId === convId;
      const isFromMe = m.senderId === s.myUserId;
      const incUnread = !isActive && !isFromMe ? 1 : 0;
      conversations = sortByLatest(
        s.conversations.map((c) =>
          c.id === convId
            ? {
                ...c,
                lastMessage: m.isRecalled ? '[已撤回]' : m.content,
                lastMessageType: m.messageType,
                lastMessageAt: m.createTime,
                unreadCount: c.unreadCount + incUnread,
              }
            : c
        )
      );
    } else {
      // 新会话:先重新拉一下列表
      get().loadConversations();
    }
    return {
      messagesByConv: { ...s.messagesByConv, [convId]: [...list, m] },
      conversations,
    };
  });
  useNotificationStore.getState().refreshUnread();
}

// 同一 peer 正在进行的建会话请求,避免并发重复创建
const pendingPeerOpens: Record<string, Promise<Conversation> | undefined> = {};

export const useChatStore = create<ChatState>((set, get) => ({
  ws: null,
  myUserId: null,
  conversations: [],
  messagesByConv: {},
  activeConvId: null,
  typingPeers: {},
  loadingMessages: false,

  connect: (token) => {
    if (get().ws) return;
    const ws = new WebSocket(buildChatWsUrl(token));
    // 兜底:WS 尚未收到 connected 事件前，先用本地登录用户 ID 判断“自己的消息”，
    // 避免左右区分（left/right）依赖 WS 的连接状态。
    const meId = useAuthStore.getState().user?.id ?? null;
    set({ ws, myUserId: meId });

    ws.onmessage = (ev) => {
      let data: any;
      try {
        data = JSON.parse(ev.data);
      } catch {
        return;
      }
      const t = data.type;
      if (t === 'connected') {
        set({ myUserId: data.userId });
      } else if (t === 'message') {
        appendIncomingMessage(set, get, data.data as ChatMessage);
      } else if (t === 'recall') {
        const { messageId, conversationId } = data;
        set((s) => {
          const list = (s.messagesByConv[conversationId] || []).map((x) =>
            x.id === messageId ? { ...x, isRecalled: true, content: '消息已撤回' } : x
          );
          return { messagesByConv: { ...s.messagesByConv, [conversationId]: list } };
        });
      } else if (t === 'read') {
        set((s) => {
          const convId = data.conversationId;
          const list = (s.messagesByConv[convId] || []).map((x) =>
            x.senderId === s.myUserId ? { ...x, isRead: true } : x
          );
          return { messagesByConv: { ...s.messagesByConv, [convId]: list } };
        });
      } else if (t === 'typing') {
        const peer = data.fromUserId;
        set((s) => ({ typingPeers: { ...s.typingPeers, [peer]: Date.now() + 3000 } }));
      }
    };

    ws.onclose = () => {
      // 只清掉 ws 连接对象；myUserId 是“当前登录用户 ID”，从 authStore 继续兜底，
      // 避免 WS 断开后左右区分（left/right）失效。
      set({ ws: null, myUserId: useAuthStore.getState().user?.id ?? null });
    };
    ws.onerror = () => {};
  },

  disconnect: () => {
    const ws = get().ws;
    if (ws) ws.close();
    set({ ws: null, myUserId: null });
  },

  loadConversations: async () => {
    const list = await listConversations();
    set({ conversations: sortByLatest(list) });
  },

  openConversationWith: (peerId) => {
    // 并发去重:React StrictMode 下 effect 会执行两次,避免对同一 peer 并发发两个建会话请求
    if (pendingPeerOpens[peerId]) return pendingPeerOpens[peerId];
    const p = openConversation(peerId)
      .then((conv) => {
        set((s) => {
          if (s.conversations.find((c) => c.id === conv.id)) return s;
          return { conversations: sortByLatest([...s.conversations, conv]) };
        });
        return conv;
      })
      .finally(() => {
        delete pendingPeerOpens[peerId];
      });
    pendingPeerOpens[peerId] = p;
    return p;
  },

  selectConversation: (convId) => {
    set({ activeConvId: convId });
    get().loadMessages(convId);
    get().markRead(convId);
  },

  loadMessages: async (convId) => {
    set({ loadingMessages: true });
    try {
      const msgs = await listMessages(convId);
      set((s) => ({ messagesByConv: { ...s.messagesByConv, [convId]: msgs } }));
    } finally {
      set({ loadingMessages: false });
    }
  },

  sendText: async (peerId, content) => {
    const ws = get().ws;
    const trimmed = content.trim();
    if (!trimmed) return;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'send', peerId, content: trimmed, messageType: 0 }));
    } else {
      // 兜底:走 HTTP，并把返回的消息写入 store（否则发送成功后必须刷新页面才显示）
      const convId = get().activeConvId;
      if (!convId) return;
      try {
        const msg = await sendMessageHttp(convId, trimmed);
        if (msg) appendIncomingMessage(set, get, msg);
      } catch (e) {
        console.error('发送私信失败:', e);
      }
    }
  },

  sendTyping: (peerId) => {
    const ws = get().ws;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'typing', peerId }));
    }
  },

  recall: async (msgId) => {
    await recallMessage(msgId);
  },

  markRead: async (convId) => {
    try {
      await markConversationRead(convId);
      set((s) => ({
        conversations: s.conversations.map((c) =>
          c.id === convId ? { ...c, unreadCount: 0 } : c
        ),
      }));
      useNotificationStore.getState().refreshUnread();
    } catch {}
  },
}));
