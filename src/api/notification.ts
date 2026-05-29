import { apiRequest } from '../api';

export interface NotificationItem {
  id: string;
  notifType: number;   // 0点赞 1评论 2关注 3@提及 4系统
  targetType: number;  // 0视频 1评论 2直播
  targetId: string;
  senderId: string;
  senderName: string;
  senderAvatar: string;
  content: string;
  isRead: boolean;
  createTime: string;
}

export interface UnreadCount {
  total: number;
  chat: number;
  notification: number;
}

export function listNotifications(opts: {
  notifType?: number;
  onlyUnread?: boolean;
  offset?: number;
  limit?: number;
} = {}) {
  const params = new URLSearchParams();
  if (opts.notifType !== undefined) params.set('notif_type', String(opts.notifType));
  if (opts.onlyUnread) params.set('only_unread', 'true');
  params.set('offset', String(opts.offset ?? 0));
  params.set('limit', String(opts.limit ?? 20));
  return apiRequest<NotificationItem[]>(`/api/notifications?${params}`);
}

export function getUnreadCount() {
  return apiRequest<UnreadCount>('/api/notifications/unread-count');
}

export function markNotificationRead(id: string) {
  return apiRequest(`/api/notifications/${id}/read`, { method: 'POST' });
}

export function markAllRead(notifType?: number) {
  const q = notifType !== undefined ? `?notif_type=${notifType}` : '';
  return apiRequest(`/api/notifications/read-all${q}`, { method: 'POST' });
}
