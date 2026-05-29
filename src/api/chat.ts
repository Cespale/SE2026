import { apiRequest, API_BASE } from '../api';

export interface ChatMessage {
  id: string;
  conversationId: string;
  senderId: string;
  senderName: string;
  senderAvatar: string;
  receiverId: string;
  content: string;
  messageType: number;
  isRecalled: boolean;
  isRead: boolean;
  createTime: string;
}

export interface Conversation {
  id: string;
  peerId: string;
  peerName: string;
  peerAvatar: string;
  lastMessage: string;
  lastMessageType: number;
  lastMessageAt: string;
  unreadCount: number;
}

export function listConversations() {
  return apiRequest<Conversation[]>('/api/chat/conversations');
}

export function openConversation(peerId: string) {
  return apiRequest<Conversation>('/api/chat/conversations', {
    method: 'POST',
    body: JSON.stringify({ peerId }),
  });
}

export function listMessages(convId: string, before?: string, limit = 50) {
  const q = new URLSearchParams({ limit: String(limit) });
  if (before) q.set('before', before);
  return apiRequest<ChatMessage[]>(`/api/chat/conversations/${convId}/messages?${q}`);
}

export function sendMessageHttp(convId: string, content: string, messageType = 0) {
  return apiRequest<ChatMessage>(`/api/chat/conversations/${convId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ content, messageType }),
  });
}

export function recallMessage(msgId: string) {
  return apiRequest(`/api/chat/messages/${msgId}/recall`, { method: 'POST' });
}

export function markConversationRead(convId: string) {
  return apiRequest(`/api/chat/conversations/${convId}/read`, { method: 'POST' });
}

export function buildChatWsUrl(token: string): string {
  const wsBase = API_BASE.replace(/^http/, 'ws');
  return `${wsBase}/ws/chat?token=${encodeURIComponent(token)}`;
}
