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

  sendText: (peerId: string, content: string) => void;
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
    set({ ws });

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
        const m: ChatMessage = data.data;
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
      set({ ws: null, myUserId: null });
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

  openConversationWith: async (peerId) => {
    const conv = await openConversation(peerId);
    set((s) => {
      if (s.conversations.find((c) => c.id === conv.id)) return s;
      return { conversations: sortByLatest([...s.conversations, conv]) };
    });
    return conv;
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

  sendText: (peerId, content) => {
    const ws = get().ws;
    const trimmed = content.trim();
    if (!trimmed) return;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'send', peerId, content: trimmed, messageType: 0 }));
    } else {
      // 兜底:走 HTTP
      const convId = get().activeConvId;
      if (convId) sendMessageHttp(convId, trimmed).catch(() => {});
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
