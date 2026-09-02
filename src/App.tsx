import React from 'react';
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';

const TopNav = React.lazy(() => import('./components/layout/TopNav').then(({ TopNav }) => ({ default: TopNav })));
const Sidebar = React.lazy(() => import('./components/layout/Sidebar').then(({ Sidebar }) => ({ default: Sidebar })));
const AuthModals = React.lazy(() => import('./components/auth/AuthModals').then(({ AuthModals }) => ({ default: AuthModals })));
const RequireAuth = React.lazy(() => import('./components/auth/RequireAuth').then(({ RequireAuth }) => ({ default: RequireAuth })));

const HomePage = React.lazy(() => import('./pages/HomePage').then(({ HomePage }) => ({ default: HomePage })));
const DiscoverPage = React.lazy(() => import('./pages/DiscoverPage').then(({ DiscoverPage }) => ({ default: DiscoverPage })));
const SearchPage = React.lazy(() => import('./pages/SearchPage').then(({ SearchPage }) => ({ default: SearchPage })));
const VideoPage = React.lazy(() => import('./pages/VideoPage').then(({ VideoPage }) => ({ default: VideoPage })));
const LivePage = React.lazy(() => import('./pages/LivePage').then(({ LivePage }) => ({ default: LivePage })));
const LiveStartPage = React.lazy(() => import('./pages/LiveStartPage').then(({ LiveStartPage }) => ({ default: LiveStartPage })));
const UploadPage = React.lazy(() => import('./pages/UploadPage').then(({ UploadPage }) => ({ default: UploadPage })));
const UserPage = React.lazy(() => import('./pages/UserPage').then(({ UserPage }) => ({ default: UserPage })));
const CreatorPage = React.lazy(() => import('./pages/CreatorPage').then(({ CreatorPage }) => ({ default: CreatorPage })));
const SettingsPage = React.lazy(() => import('./pages/SettingsPage').then(({ SettingsPage }) => ({ default: SettingsPage })));
const AdminPage = React.lazy(() => import('./pages/AdminPage').then(({ AdminPage }) => ({ default: AdminPage })));
const ShortVideoPage = React.lazy(() => import('./pages/ShortVideoPage').then(({ ShortVideoPage }) => ({ default: ShortVideoPage })));
const SubscriptionPage = React.lazy(() => import('./pages/SubscriptionPage').then(({ SubscriptionPage }) => ({ default: SubscriptionPage })));
const ProfilePage = React.lazy(() => import('./pages/ProfilePage').then(({ ProfilePage }) => ({ default: ProfilePage })));
const ExplorePage = React.lazy(() => import('./pages/ExplorePage').then(({ ExplorePage }) => ({ default: ExplorePage })));
const NotificationPage = React.lazy(() => import('./pages/NotificationPage').then(({ NotificationPage }) => ({ default: NotificationPage })));
const MessagePage = React.lazy(() => import('./pages/MessagePage').then(({ MessagePage }) => ({ default: MessagePage })));

function App() {
  return (
    <HashRouter>
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
        <React.Suspense fallback={null}>
          <TopNav />
          <Sidebar />
        </React.Suspense>

        <main className="pt-16 pl-16 md:pl-56">
          <React.Suspense fallback={<div className="p-8 text-gray-500">页面加载中...</div>}>
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
                <RequireAuth message="请先登录后再查看动态。">
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
          </React.Suspense>
        </main>

        <React.Suspense fallback={null}>
          <AuthModals />
        </React.Suspense>
      </div>
    </HashRouter>
  );
}

export default App;
