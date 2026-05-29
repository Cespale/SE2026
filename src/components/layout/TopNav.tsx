import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Search,
  User,
  LogOut,
  Settings,
  Video,
  LayoutDashboard,
  Upload,
  Radio,
  Shield,
} from 'lucide-react';
import { useAuthStore } from '../../stores/authStore';
import { NotificationBell } from '../notification/NotificationBell';
import { MessageButton } from '../notification/MessageButton';

const DEFAULT_AVATAR =
  'https://api.dicebear.com/7.x/avataaars/svg?seed=user';

export function TopNav() {
  const navigate = useNavigate();

  const {
    user,
    isLoggedIn,
    logout,
    openLoginModal,
    openRegisterModal,
  } = useAuthStore();

  const [searchKeyword, setSearchKeyword] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);

  const userType = Number(user?.userType ?? 0);
  const userId = user?.id || '';
  const nickname = user?.nickname || '用户';
  const avatar = user?.avatar || DEFAULT_AVATAR;

  const isCreator = userType >= 1;
  const isAdmin = userType === 2;

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();

    const keyword = searchKeyword.trim();

    if (!keyword) return;

    navigate(`/search?keyword=${encodeURIComponent(keyword)}`);
  };

  const handleLogout = () => {
    logout();
    setShowDropdown(false);
    navigate('/');
  };

  const goAndClose = (path: string) => {
    setShowDropdown(false);
    navigate(path);
  };

  return (
    <nav className="fixed top-0 left-0 right-0 h-16 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 z-50">
      <div className="max-w-7xl mx-auto px-4 h-full flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2 flex-shrink-0">
          <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
            <Video className="w-5 h-5 text-white" />
          </div>

          <span className="text-xl font-bold text-gray-900 dark:text-white">
            StreamHub
          </span>
        </Link>

        <form
          onSubmit={handleSearch}
          className="hidden md:block flex-1 max-w-md mx-8"
        >
          <div className="relative">
            <input
              type="text"
              value={searchKeyword}
              onChange={(e) => setSearchKeyword(e.target.value)}
              placeholder="搜索视频、直播..."
              className="w-full h-10 pl-10 pr-4 bg-gray-100 dark:bg-gray-800 border-0 rounded-full text-sm text-gray-900 dark:text-white placeholder-gray-500 focus:ring-2 focus:ring-blue-500 focus:bg-white dark:focus:bg-gray-800 transition-all"
            />

            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          </div>
        </form>

        <div className="flex items-center gap-3">
          {isLoggedIn && isCreator && (
            <button
              onClick={() => navigate('/upload')}
              className="hidden sm:flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-full transition-colors"
            >
              <Upload className="w-4 h-4" />
              投稿
            </button>
          )}

          <MessageButton />
          <NotificationBell />

          {isLoggedIn ? (
            <div className="relative">
              <button
                onClick={() => setShowDropdown((prev) => !prev)}
                className="flex items-center gap-2 p-1 rounded-full hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
              >
                <img
                  src={avatar}
                  alt={nickname}
                  className="w-8 h-8 rounded-full object-cover bg-gray-200"
                  onError={(e) => {
                    const target = e.currentTarget;

                    if (target.src !== DEFAULT_AVATAR) {
                      target.src = DEFAULT_AVATAR;
                    }
                  }}
                />

                <span className="text-sm font-medium text-gray-900 dark:text-white hidden sm:block max-w-24 truncate">
                  {nickname}
                </span>
              </button>

              {showDropdown && (
                <div className="absolute right-0 top-full mt-2 w-56 bg-white dark:bg-gray-900 rounded-lg shadow-lg border border-gray-200 dark:border-gray-800 py-2 overflow-hidden">
                  <button
                    onClick={() => goAndClose(`/user/${userId}`)}
                    className="flex items-center gap-3 px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 w-full text-left"
                  >
                    <User className="w-4 h-4" />
                    个人主页
                  </button>

                  {isCreator && (
                    <>
                      <button
                        onClick={() => goAndClose('/upload')}
                        className="flex items-center gap-3 px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 w-full text-left"
                      >
                        <Upload className="w-4 h-4" />
                        上传视频
                      </button>

                      <button
                        onClick={() => goAndClose('/creator')}
                        className="flex items-center gap-3 px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 w-full text-left"
                      >
                        <LayoutDashboard className="w-4 h-4" />
                        创作者中心
                      </button>

                      <button
                        onClick={() => goAndClose('/live/start')}
                        className="flex items-center gap-3 px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 w-full text-left"
                      >
                        <Radio className="w-4 h-4" />
                        开始直播
                      </button>
                    </>
                  )}

                  {isAdmin && (
                    <button
                      onClick={() => goAndClose('/admin')}
                      className="flex items-center gap-3 px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 w-full text-left"
                    >
                      <Shield className="w-4 h-4" />
                      管理后台
                    </button>
                  )}

                  <button
                    onClick={() => goAndClose('/settings')}
                    className="flex items-center gap-3 px-4 py-2 text-sm text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 w-full text-left"
                  >
                    <Settings className="w-4 h-4" />
                    设置
                  </button>

                  <div className="border-t border-gray-200 dark:border-gray-800 my-1" />

                  <button
                    onClick={handleLogout}
                    className="flex items-center gap-3 px-4 py-2 text-sm text-red-600 hover:bg-gray-100 dark:hover:bg-gray-800 w-full text-left"
                  >
                    <LogOut className="w-4 h-4" />
                    退出登录
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <button
                onClick={openLoginModal}
                className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white transition-colors"
              >
                登录
              </button>

              <button
                onClick={openRegisterModal}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-full transition-colors"
              >
                注册
              </button>
            </div>
          )}
        </div>
      </div>
    </nav>
  );
}

export default TopNav;