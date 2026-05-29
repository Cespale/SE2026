import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell } from 'lucide-react';
import { useNotificationStore } from '../../stores/notificationStore';
import { useAuthStore } from '../../stores/authStore';

export function NotificationBell() {
  const navigate = useNavigate();
  const { isLoggedIn } = useAuthStore();
  const unread = useNotificationStore((s) => s.unread);
  const startPolling = useNotificationStore((s) => s.startPolling);
  const stopPolling = useNotificationStore((s) => s.stopPolling);

  useEffect(() => {
    if (isLoggedIn) {
      startPolling();
      return () => stopPolling();
    }
  }, [isLoggedIn]);

  if (!isLoggedIn) return null;

  const count = unread.notification;
  const display = count > 99 ? '99+' : String(count);

  return (
    <button
      onClick={() => navigate('/notifications')}
      className="relative p-2 rounded-full hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
      title="通知"
    >
      <Bell className="w-5 h-5 text-gray-700 dark:text-gray-300" />
      {count > 0 && (
        <span className="absolute top-0 right-0 min-w-[18px] h-[18px] px-1 flex items-center justify-center text-[10px] font-bold text-white bg-red-500 rounded-full">
          {display}
        </span>
      )}
    </button>
  );
}
