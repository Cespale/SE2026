import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import {
  Home,
  PlaySquare,
  Heart,
  User,
  Compass,
  Upload,
  LayoutDashboard,
  Shield,
  Radio,
} from 'lucide-react';
import { motion } from 'framer-motion';
import { useAuthStore } from '../../stores/authStore';

const baseMenuItems = [
  { id: 'home', label: '首页', icon: Home, path: '/' },
  { id: 'discover', label: '发现/直播', icon: Compass, path: '/discover' },
  { id: 'shorts', label: '短视频', icon: PlaySquare, path: '/shorts' },
  { id: 'subscriptions', label: '订阅', icon: Heart, path: '/subscriptions' },
  { id: 'profile', label: '我的', icon: User, path: '/profile' },
];

const creatorMenuItems = [
  { id: 'upload', label: '上传视频', icon: Upload, path: '/upload' },
  { id: 'creator', label: '创作者中心', icon: LayoutDashboard, path: '/creator' },
  { id: 'live-start', label: '开始直播', icon: Radio, path: '/live/start' },
];

const adminMenuItems = [
  { id: 'admin', label: '管理后台', icon: Shield, path: '/admin' },
];

function isActivePath(currentPath: string, itemPath: string) {
  if (itemPath === '/') {
    return currentPath === '/';
  }

  return currentPath === itemPath || currentPath.startsWith(`${itemPath}/`);
}

export function Sidebar() {
  const location = useLocation();
  const { user, isLoggedIn } = useAuthStore();

  const userType = Number(user?.userType ?? 0);
  const isCreator = isLoggedIn && userType >= 1;
  const isAdmin = isLoggedIn && userType === 2;

  // 登录后:"我的" 链接到自己的用户主页(与右上角"个人主页"一致)
  const myProfilePath = isLoggedIn && user?.id ? `/user/${user.id}` : '/profile';

  const menuItems = [
    ...baseMenuItems.map((item) =>
      item.id === 'profile' ? { ...item, path: myProfilePath } : item
    ),
    ...(isCreator ? creatorMenuItems : []),
    ...(isAdmin ? adminMenuItems : []),
  ];

  return (
    <aside className="fixed left-0 top-16 bottom-0 w-16 md:w-56 bg-white dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800 z-40">
      <nav className="p-2 space-y-1">
        {menuItems.map((item) => {
          const Icon = item.icon;
          const isActive = isActivePath(location.pathname, item.path);

          return (
            <Link
              key={item.id}
              to={item.path}
              title={item.label}
              className={`relative flex items-center gap-3 px-3 py-3 rounded-xl transition-all duration-200 group ${
                isActive
                  ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400'
                  : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800'
              }`}
            >
              {isActive && (
                <motion.div
                  layoutId="activeSidebarIndicator"
                  className="absolute left-0 w-1 h-8 bg-blue-500 rounded-r-full hidden md:block"
                  initial={false}
                  transition={{
                    type: 'spring',
                    stiffness: 500,
                    damping: 30,
                  }}
                />
              )}

              <Icon
                className={`w-6 h-6 flex-shrink-0 transition-transform group-hover:scale-110 ${
                  isActive ? 'text-blue-600 dark:text-blue-400' : ''
                }`}
              />

              <span className="hidden md:block font-medium text-sm truncate">
                {item.label}
              </span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}

export default Sidebar;