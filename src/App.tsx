import React from 'react';
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';
import { TopNav } from './components/layout/TopNav';
import { Sidebar } from './components/layout/Sidebar';

import { HomePage } from './pages/HomePage';
import { DiscoverPage } from './pages/DiscoverPage';
import { SearchPage } from './pages/SearchPage';
import { VideoPage } from './pages/VideoPage';
import { LivePage } from './pages/LivePage';
import { LiveStartPage } from './pages/LiveStartPage';
import { UploadPage } from './pages/UploadPage';
import { UserPage } from './pages/UserPage';
import { CreatorPage } from './pages/CreatorPage';
import { SettingsPage } from './pages/SettingsPage';
import { AdminPage } from './pages/AdminPage';
import { ShortVideoPage } from './pages/ShortVideoPage';
import { SubscriptionPage } from './pages/SubscriptionPage';
import { ProfilePage } from './pages/ProfilePage';
import { ExplorePage } from './pages/ExplorePage';
import { NotificationPage } from './pages/NotificationPage';
import { MessagePage } from './pages/MessagePage';

import { LoginModal } from './components/auth/LoginModal';
import { RegisterModal } from './components/auth/RegisterModal';
import { RequireAuth } from './components/auth/RequireAuth';
import { useAuthStore } from './stores/authStore';

function App() {
  const {
    showLoginModal,
    showRegisterModal,
    closeLoginModal,
    closeRegisterModal,
    openRegisterModal,
    openLoginModal,
  } = useAuthStore();

  return (
    <HashRouter>
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
        <TopNav />
        <Sidebar />

        <main className="pt-16 pl-16 md:pl-56">
          <Routes>
            <Route path="/" element={<HomePage />} />

            <Route path="/shorts" element={<ShortVideoPage />} />
            <Route path="/explore" element={<ExplorePage />} />
            <Route path="/discover" element={<DiscoverPage />} />
            <Route path="/search" element={<SearchPage />} />

            <Route path="/video/:id" element={<VideoPage />} />
            <Route path="/live/:roomId" element={<LivePage />} />
            <Route path="/user/:id" element={<UserPage />} />

            <Route
              path="/subscriptions"
              element={
                <RequireAuth message="请先登录后再查看订阅内容。">
                  <SubscriptionPage />
                </RequireAuth>
              }
            />

            <Route
              path="/profile"
              element={
                <RequireAuth message="请先登录后再查看个人主页。">
                  <ProfilePage />
                </RequireAuth>
              }
            />

            <Route
              path="/notifications"
              element={
                <RequireAuth message="请先登录后再查看通知。">
                  <NotificationPage />
                </RequireAuth>
              }
            />

            <Route
              path="/messages"
              element={
                <RequireAuth message="请先登录后再使用私信。">
                  <MessagePage />
                </RequireAuth>
              }
            />

            <Route
              path="/settings"
              element={
                <RequireAuth message="请先登录后再进入设置页面。">
                  <SettingsPage />
                </RequireAuth>
              }
            />

            <Route
              path="/upload"
              element={
                <RequireAuth
                  minUserType={1}
                  message="请先使用创作者账号登录后再上传视频。"
                >
                  <UploadPage />
                </RequireAuth>
              }
            />

            <Route
              path="/creator"
              element={
                <RequireAuth
                  minUserType={1}
                  message="请先使用创作者账号登录后再进入创作者中心。"
                >
                  <CreatorPage />
                </RequireAuth>
              }
            />

            <Route
              path="/live/start"
              element={
                <RequireAuth
                  minUserType={1}
                  message="请先使用创作者账号登录后再开播。"
                >
                  <LiveStartPage />
                </RequireAuth>
              }
            />

            <Route
              path="/admin"
              element={
                <RequireAuth
                  minUserType={2}
                  message="只有管理员账号可以进入管理后台。"
                >
                  <AdminPage />
                </RequireAuth>
              }
            />

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>

        {showLoginModal && (
          <LoginModal
            onClose={closeLoginModal}
            onRegister={openRegisterModal}
          />
        )}

        {showRegisterModal && (
          <RegisterModal
            onClose={closeRegisterModal}
            onLogin={openLoginModal}
          />
        )}
      </div>
    </HashRouter>
  );
}

export default App;