import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell, Heart, MessageCircle, UserPlus, AtSign, Megaphone } from 'lucide-react';
import { useNotificationStore } from '../stores/notificationStore';
import { NotificationItem } from '../api/notification';

type TabKey = 'all' | 0 | 1 | 2 | 3 | 4;

const TABS: { key: TabKey; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { key: 'all', label: '全部', icon: Bell },
  { key: 0, label: '点赞', icon: Heart },
  { key: 1, label: '评论', icon: MessageCircle },
  { key: 2, label: '关注', icon: UserPlus },
  { key: 3, label: '提及', icon: AtSign },
  { key: 4, label: '系统', icon: Megaphone },
];

function timeAgo(iso: string): string {
  if (!iso) return '';
  const t = new Date(iso).getTime();
  const diff = Date.now() - t;
  if (diff < 60_000) return '刚刚';
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} 分钟前`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} 小时前`;
  if (diff < 30 * 86_400_000) return `${Math.floor(diff / 86_400_000)} 天前`;
  return new Date(iso).toLocaleDateString();
}

function getTargetLink(n: NotificationItem): string | null {
  if (!n.targetId) return null;
  if (n.targetType === 0) return `/video/${n.targetId}`;
  if (n.targetType === 2) return `/live/${n.targetId}`;
  return null;
}

export function NotificationPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<TabKey>('all');
  const { items, loading, loadList, markOneRead, markAllRead } = useNotificationStore();

  useEffect(() => {
    loadList(tab === 'all' ? undefined : (tab as number));
  }, [tab]);

  function handleClick(n: NotificationItem) {
    if (!n.isRead) markOneRead(n.id);
    const link = getTargetLink(n);
    if (link) navigate(link);
    else if (n.notifType === 2 && n.senderId) navigate(`/user/${n.senderId}`);
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="max-w-3xl mx-auto px-4 py-8">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <Bell className="w-6 h-6" />
            通知
          </h1>
          <button
            onClick={() => markAllRead(tab === 'all' ? undefined : (tab as number))}
            className="text-sm text-blue-500 hover:text-blue-600"
          >
            全部标为已读
          </button>
        </div>

        <div className="flex items-center gap-1 border-b border-gray-200 dark:border-gray-800 mb-4 overflow-x-auto">
          {TABS.map((t) => {
            const Icon = t.icon;
            const active = tab === t.key;
            return (
              <button
                key={String(t.key)}
                onClick={() => setTab(t.key)}
                className={`flex items-center gap-1.5 px-4 py-3 text-sm font-medium whitespace-nowrap transition-colors ${
                  active
                    ? 'text-blue-500 border-b-2 border-blue-500'
                    : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
                }`}
              >
                <Icon className="w-4 h-4" />
                {t.label}
              </button>
            );
          })}
        </div>

        {loading ? (
          <div className="text-center py-12 text-gray-400">加载中...</div>
        ) : items.length === 0 ? (
          <div className="text-center py-20 text-gray-500">
            <Bell className="w-16 h-16 mx-auto mb-4 opacity-30" />
            <p>暂无通知</p>
          </div>
        ) : (
          <div className="space-y-2">
            {items.map((n) => (
              <div
                key={n.id}
                onClick={() => handleClick(n)}
                className={`flex items-start gap-3 p-4 rounded-xl cursor-pointer transition-colors ${
                  n.isRead
                    ? 'bg-white dark:bg-gray-800'
                    : 'bg-blue-50 dark:bg-blue-900/20 hover:bg-blue-100 dark:hover:bg-blue-900/30'
                }`}
              >
                <img
                  src={n.senderAvatar || 'https://api.dicebear.com/7.x/avataaars/svg?seed=system'}
                  alt={n.senderName}
                  className="w-10 h-10 rounded-full flex-shrink-0"
                />
                <div className="flex-1 min-w-0">
                  <div className="text-sm text-gray-900 dark:text-white">
                    <span className="font-semibold">{n.senderName}</span>{' '}
                    <span className="text-gray-600 dark:text-gray-400">{n.content}</span>
                  </div>
                  <div className="text-xs text-gray-400 mt-1">{timeAgo(n.createTime)}</div>
                </div>
                {!n.isRead && (
                  <span className="w-2 h-2 bg-red-500 rounded-full mt-2 flex-shrink-0" />
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
