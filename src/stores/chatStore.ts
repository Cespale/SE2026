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

type ChatSetState = (
  partial:
    | ChatState
    | Partial<ChatState>
    | ((state: ChatState) => ChatState | Partial<ChatState>)
) => void;

function appendIncomingMessage(
  set: ChatSetState,
  get: () => ChatState,
  message: ChatMessage
) {
  const convId = message.conversationId;
  set((state) => {
    const messages = state.messagesByConv[convId] || [];
    if (messages.some((item) => item.id === message.id)) return state;

    const conversation = state.conversations.find((item) => item.id === convId);
    let conversations = state.conversations;
    if (conversation) {
      const isActive = state.activeConvId === convId;
      const isFromMe = message.senderId === state.myUserId;
      const unreadIncrement = !isActive && !isFromMe ? 1 : 0;
      conversations = sortByLatest(
        state.conversations.map((item) =>
          item.id === convId
            ? {
                ...item,
                lastMessage: message.isRecalled ? '[已撤回]' : message.content,
                lastMessageType: message.messageType,
                lastMessageAt: message.createTime,
                unreadCount: item.unreadCount + unreadIncrement,
              }
            : item
        )
      );
    } else {
      get().loadConversations();
    }

    return {
      messagesByConv: {
        ...state.messagesByConv,
        [convId]: [...messages, message],
      },
      conversations,
    };
  });
  useNotificationStore.getState().refreshUnread();
}

const pendingPeerOpens: Record<
  string,
  Promise<Conversation> | undefined
> = {};

export const useChatStore = create<ChatState>((set, get) => ({
  ws: null,
  myUserId: null,
  conversations: [],
  messagesByConv: {},
  activeConvId: null,
  typingPeers: {},
  loadingMessages: false,

  connect: (token) => {
    const current = get().ws;
    if (
      current &&
      (current.readyState === WebSocket.CONNECTING ||
        current.readyState === WebSocket.OPEN)
    ) {
      return;
    }
    const ws = new WebSocket(buildChatWsUrl(token));
    set({
      ws,
      myUserId: useAuthStore.getState().user?.id ?? null,
    });

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
      if (get().ws !== ws) return;
      set({
        ws: null,
        myUserId: useAuthStore.getState().user?.id ?? null,
      });
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
    const pending = pendingPeerOpens[peerId];
    if (pending) return pending;

    const request = openConversation(peerId)
      .then((conversation) => {
        set((state) => {
          if (state.conversations.some((item) => item.id === conversation.id)) {
            return state;
          }
          return {
            conversations: sortByLatest([
              ...state.conversations,
              conversation,
            ]),
          };
        });
        return conversation;
      })
      .finally(() => {
        delete pendingPeerOpens[peerId];
      });
    pendingPeerOpens[peerId] = request;
    return request;
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
      const convId = get().activeConvId;
      if (!convId) return;
      try {
        const message = await sendMessageHttp(convId, trimmed);
        appendIncomingMessage(set, get, message);
      } catch (error) {
        console.error('发送私信失败:', error);
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
