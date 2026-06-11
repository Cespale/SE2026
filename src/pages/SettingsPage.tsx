import React, { useState, useRef } from 'react';
import { motion } from 'framer-motion';
import { Camera, Lock, User, FileText, Save } from 'lucide-react';
import { useAuthStore } from '../stores/authStore';
import { changePassword } from '../api';

export const SettingsPage: React.FC = () => {
  const { user, updateUser } = useAuthStore();
  const [nickname, setNickname] = useState(user?.nickname || '');
  const [bio, setBio] = useState(user?.bio || '');
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState<'success' | 'error'>('success'); 
  const [isUpgrading, setIsUpgrading] = useState(false);
  const [isPasswordExpanded, setIsPasswordExpanded] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSaveProfile = () => {
    updateUser({ nickname, bio });
    setMessage('资料已保存');
    setTimeout(() => setMessage(''), 2000);
  };

  const handleChangePassword = async () => {
    if (newPassword !== confirmPassword) {
      setMessage('两次密码不一致');
      return;
    }
    if (newPassword.length < 6) {
      setMessage('密码至少6位');
      return;
    }
    if (!oldPassword) {
      setMessage('请输入原密码');
      return;
    }

    try {
      await changePassword(oldPassword, newPassword);
      setMessage('密码修改成功，请重新登录');
      setOldPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setTimeout(() => {
        useAuthStore.getState().logout();
        window.location.href = '/';
      }, 3000);
    } catch (error: any) {
      const msg = error.message || '修改失败';
      setMessage(msg);
    }
    setTimeout(() => setMessage(''), 3000);
  };

  const handleUpgradeToCreator = async () => {
    if (!confirm('确定要升级为创作者吗？\n\n升级后你将可以：\n• 上传视频\n• 开启直播\n• 查看数据分析\n\n确定要升级吗？')) {
      return;
    }
    
    setIsUpgrading(true);
    try {
      const { upgradeToCreator } = useAuthStore.getState();
      const success = await upgradeToCreator();
      
      if (success) {
        setMessageType('success');
        setMessage('恭喜！已成功升级为创作者，刷新页面后即可看到新功能');
        await useAuthStore.getState().refreshMe();
      } else {
        setMessageType('error');
        setMessage('升级失败，请稍后重试');
      }
    } catch (error) {
      setMessageType('error');
      setMessage('升级失败，请稍后重试');
    } finally {
      setIsUpgrading(false);
      setTimeout(() => setMessage(''), 3000);
    }
  };

  const handleAvatarUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    
    if (!file.type.startsWith('image/')) {
      setMessageType('error');
      setMessage('请选择图片文件');
      setTimeout(() => setMessage(''), 3000);
      return;
    }
    
    if (file.size > 2 * 1024 * 1024) {
      setMessageType('error');
      setMessage('图片大小不能超过2MB');
      setTimeout(() => setMessage(''), 3000);
      return;
    }
    
    setIsUploading(true);
    
    try {
      const token = localStorage.getItem('auth-storage') 
        ? JSON.parse(localStorage.getItem('auth-storage')!).state?.token 
        : '';
      
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await fetch('http://localhost:8000/api/auth/upload-avatar', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`
        },
        body: formData
      });
      
      const data = await response.json();
      
      if (response.ok) {
        const currentUser = useAuthStore.getState().user;
        if (currentUser && data.data?.avatar) {
          useAuthStore.setState({
            user: {
              ...currentUser,
              avatar: data.data.avatar
            }
          });
        }
        setMessageType('success');
        setMessage('头像更新成功');
        setTimeout(() => setMessage(''), 3000);
      } else {
        throw new Error(data.detail || '上传失败');
      }
    } catch (error: any) {
      setMessageType('error');
      setMessage(error.message || '上传失败');
      setTimeout(() => setMessage(''), 3000);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 py-8">
      <div className="max-w-7xl mx-auto px-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm p-8 w-full"
        >
          <h1 className="text-2xl font-bold mb-8">个人设置</h1>

          {message && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className={`mb-6 p-3 rounded-lg ${
                messageType === 'success' 
                  ? 'bg-green-100 text-green-700' 
                  : 'bg-red-100 text-red-700'
              }`}
            >
              {message}
            </motion.div>
          )}

          {/* 头像 */}
          <div className="mb-8">
            <label className="block text-sm font-medium mb-3">头像</label>
            <div className="flex items-center gap-4">
              <img
                src={user?.avatar}
                alt="avatar"
                className="w-20 h-20 rounded-full object-cover"
              />
              <div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handleAvatarUpload}
                  className="hidden"
                  id="avatar-upload"
                />
                <label
                  htmlFor="avatar-upload"
                  className={`inline-flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 cursor-pointer ${
                    isUploading ? 'opacity-50 pointer-events-none' : ''
                  }`}
                >
                  <Camera className="w-4 h-4" />
                  {isUploading ? '上传中...' : '更换头像'}
                </label>
              </div>
            </div>
          </div>

          {/* 昵称 */}
          <div className="mb-6">
            <label className="block text-sm font-medium mb-2">
              <User className="w-4 h-4 inline mr-1" />
              昵称
            </label>
            <input
              type="text"
              value={nickname}
              onChange={(e) => setNickname(e.target.value)}
              readOnly={!isEditing}
              className={`w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 transition-colors ${
                isEditing
                  ? 'bg-white dark:bg-gray-700 border-gray-300 dark:border-gray-600'
                  : 'bg-gray-50 dark:bg-gray-800 border-transparent cursor-default'
              }`}
              placeholder="2-20字"
            />
          </div>

          {/* 简介 */}
          <div className="mb-6">
            <label className="block text-sm font-medium mb-2">
              <FileText className="w-4 h-4 inline mr-1" />
              简介
            </label>
            <textarea
              value={bio}
              onChange={(e) => setBio(e.target.value)}
              readOnly={!isEditing}
              rows={3}
              className={`w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 transition-colors resize-none ${
                isEditing
                  ? 'bg-white dark:bg-gray-700 border-gray-300 dark:border-gray-600'
                  : 'bg-gray-50 dark:bg-gray-800 border-transparent cursor-default'
              }`}
              placeholder="介绍一下自己"
            />
          </div>

          <div className="flex gap-3">
            {!isEditing ? (
              <button
                onClick={() => setIsEditing(true)}
                className="flex items-center gap-2 px-6 py-2 bg-gray-500 text-white rounded-lg hover:bg-gray-600"
              >
                编辑资料
              </button>
            ) : (
              <>
                <button
                  onClick={() => {
                    setIsEditing(false);
                    setNickname(user?.nickname || '');
                    setBio(user?.bio || '');
                  }}
                  className="flex items-center gap-2 px-6 py-2 bg-gray-300 text-gray-700 rounded-lg hover:bg-gray-400"
                >
                  取消
                </button>
                <button
                  onClick={handleSaveProfile}
                  className="flex items-center gap-2 px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
                >
                  <Save className="w-4 h-4" />
                  保存资料
                </button>
              </>
            )}
          </div>

          {/* 修改密码 - 可折叠 */}
          <div className="border-t my-8" />

          <button
            onClick={() => setIsPasswordExpanded(!isPasswordExpanded)}
            className="w-full flex items-center justify-between text-left"
          >
            <h2 className="text-lg font-semibold">
              <Lock className="w-5 h-5 inline mr-2" />
              修改密码
            </h2>
            <svg
              className={`w-5 h-5 transition-transform duration-200 ${isPasswordExpanded ? 'rotate-180' : ''}`}
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {isPasswordExpanded && (
            <div className="space-y-4 mt-4">
              <input
                type="password"
                value={oldPassword}
                onChange={(e) => setOldPassword(e.target.value)}
                placeholder="原密码"
                className="w-full px-4 py-2 border rounded-lg"
              />
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="新密码"
                className="w-full px-4 py-2 border rounded-lg"
              />
              <input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="确认新密码"
                className="w-full px-4 py-2 border rounded-lg"
              />
              <button
                onClick={handleChangePassword}
                className="px-6 py-2 bg-gray-800 text-white rounded-lg hover:bg-gray-900"
              >
                修改密码
              </button>
            </div>
          )}

          {/* 成为创作者按钮 - 仅普通用户显示 */}
          {user?.userType === 0 && (
            <div className="mt-8 pt-6 border-t border-gray-200 dark:border-gray-700">
              <div className="bg-gradient-to-r from-purple-50 to-pink-50 dark:from-purple-900/20 dark:to-pink-900/20 rounded-lg p-5">
                <h3 className="text-lg font-semibold mb-2 text-gray-900 dark:text-white">
                  🎬 成为创作者
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                  升级后可以上传视频、开启直播，获得更多创作工具和数据分析功能
                </p>
                <button
                  onClick={handleUpgradeToCreator}
                  disabled={isUpgrading}
                  className="px-6 py-2 bg-gradient-to-r from-purple-500 to-pink-500 text-white rounded-lg hover:from-purple-600 hover:to-pink-600 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isUpgrading ? '处理中...' : '立即升级'}
                </button>
              </div>
            </div>
          )}
        </motion.div>
      </div>
    </div>
  );
};

export default SettingsPage;