import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Video, Copy, Check, AlertCircle, Loader2, Image as ImageIcon, X } from 'lucide-react';
import { useAuthStore } from '../stores/authStore';
import { useLiveStore } from '../stores/liveStore';
import { apiRequest, API_BASE } from '../api';

const DEFAULT_COVER = 'https://images.unsplash.com/photo-1611162616475-46b635cb6868?w=900&auto=format&fit=crop';

export function LiveStartPage() {
  const navigate = useNavigate();
  const { isLoggedIn, user, openLoginModal } = useAuthStore();
  const { createRoom } = useLiveStore();

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [coverUrl, setCoverUrl] = useState(DEFAULT_COVER);
  const [coverFile, setCoverFile] = useState<File | null>(null);
  const [coverPreview, setCoverPreview] = useState('');
  const [isUploadingCover, setIsUploadingCover] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [copied, setCopied] = useState<string | null>(null);
  const [existingRoom, setExistingRoom] = useState<any>(null);
  const [isChecking, setIsChecking] = useState(true);
  const [userStreamKey, setUserStreamKey] = useState<string>('');

  const coverInputRef = useRef<HTMLInputElement>(null);

  const userType = Number(user?.userType ?? 0);

  // 获取用户的 streamKey
  useEffect(() => {
    const fetchStreamKey = async () => {
      if (!isLoggedIn || userType < 1) return;
      try {
        const data = await apiRequest('/api/auth/me');
        console.log('获取到用户信息:', data);
        setUserStreamKey(data.streamKey || '');
      } catch (e) {
        console.error('获取streamKey失败', e);
      }
    };
    fetchStreamKey();
  }, [isLoggedIn, userType]);

  // 检查是否有正在直播的房间
  useEffect(() => {
    const check = async () => {
      if (!isLoggedIn || userType < 1) {
        setIsChecking(false);
        return;
      }
      try {
        const rooms = await apiRequest('/api/live/rooms');
        const active = rooms.items?.find((r: any) => r.anchorId === user?.id && r.status === 1);
        setExistingRoom(active);
      } catch (e) {
        console.error(e);
      } finally {
        setIsChecking(false);
      }
    };
    check();
  }, [isLoggedIn, userType, user?.id]);

  // 处理封面上传
  const handleCoverUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    if (!file.type.startsWith('image/')) {
      alert('请选择图片文件');
      return;
    }
    
    if (file.size > 2 * 1024 * 1024) {
      alert('图片大小不能超过2MB');
      return;
    }
    
    setCoverFile(file);
    const previewUrl = URL.createObjectURL(file);
    setCoverPreview(previewUrl);
    
    setIsUploadingCover(true);
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      const token = localStorage.getItem('auth-storage') 
        ? JSON.parse(localStorage.getItem('auth-storage')!).state?.token 
        : '';
      const response = await fetch(`${API_BASE}/api/videos/upload-cover`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
        body: formData
      });
      const data = await response.json();
      if (response.ok) {
        setCoverUrl(data.data.coverUrl);
      } else {
        console.error('封面上传失败');
      }
    } catch (err) {
      console.error('封面上传失败', err);
    } finally {
      setIsUploadingCover(false);
    }
  };

  // 移除封面
  const removeCover = () => {
    if (coverPreview) {
      URL.revokeObjectURL(coverPreview);
    }
    setCoverFile(null);
    setCoverPreview('');
    setCoverUrl(DEFAULT_COVER);
    if (coverInputRef.current) {
      coverInputRef.current.value = '';
    }
  };

  const handleStart = async () => {
    if (!title.trim()) {
      setErrorMsg('请填写直播间标题');
      return;
    }

    setIsLoading(true);
    setErrorMsg('');

    const room = await createRoom(title.trim(), '10', coverUrl, description.trim());
    setIsLoading(false);

    if (room) {
      navigate(`/live/${room.id}`);
    } else {
      setErrorMsg('创建直播间失败');
    }
  };

  const copyToClipboard = async (text: string, type: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(type);
      setTimeout(() => setCopied(null), 2000);
    } catch {
      alert('复制失败');
    }
  };

  if (!isLoggedIn) {
    return (
      <div className="min-h-[70vh] flex items-center justify-center px-4">
        <div className="text-center bg-white dark:bg-gray-800 rounded-2xl p-8 max-w-sm">
          <AlertCircle className="w-16 h-16 text-blue-500 mx-auto mb-4" />
          <h2 className="text-xl font-bold mb-2">请先登录</h2>
          <p className="text-gray-500 mb-6">登录创作者账号后才能开播</p>
          <button onClick={openLoginModal} className="px-6 py-2 bg-blue-600 text-white rounded-full">
            去登录
          </button>
        </div>
      </div>
    );
  }

  if (userType < 1) {
    return (
      <div className="min-h-[70vh] flex items-center justify-center px-4">
        <div className="text-center bg-white dark:bg-gray-800 rounded-2xl p-8 max-w-sm">
          <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-bold mb-2">无权限开播</h2>
          <p className="text-gray-500 mb-6">请使用创作者账号登录</p>
          <button onClick={() => navigate('/')} className="px-6 py-2 bg-blue-600 text-white rounded-full">
            返回首页
          </button>
        </div>
      </div>
    );
  }

  if (isChecking) {
    return (
      <div className="min-h-[70vh] flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  // 有正在直播的房间
  if (existingRoom) {
    // 推流密钥必须以房间的 streamKey 为准：观众拉流的 pullUrl 就是按 room.streamKey 生成的，
    // 推流 key 与它不一致则推上来观众也看不到（OBS 连接成功但流名对不上）。
    const streamKey = existingRoom.streamKey || userStreamKey;
    const pushUrl = `rtmp://${window.location.hostname}:1935/live`;

    const handleStopLive = async () => {
      if (!confirm('确定要结束直播吗？')) return;
      try {
        await apiRequest(`/api/live/rooms/${existingRoom.id}/stop`, { method: 'POST' });
        setExistingRoom(null);
        alert('直播已结束');
      } catch (error) {
        alert('结束失败，请重试');
      }
    };

    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 py-12">
        <div className="max-w-7xl mx-auto px-4">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
            className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg p-8"
          >
            <div className="flex items-center gap-3 mb-6">
              <div className="w-12 h-12 bg-red-500 rounded-xl flex items-center justify-center">
                <Video className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold">直播中</h1>
                <p className="text-gray-500">当前直播间正在推流</p>
              </div>
            </div>

            <div className="bg-red-50 dark:bg-red-900/20 rounded-lg p-4 mb-6">
              <p className="font-medium">{existingRoom.title}</p>
              {existingRoom.description && <p className="text-sm text-gray-500 mt-1">{existingRoom.description}</p>}
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2">推流地址</label>
                <div className="flex gap-2">
                  <input readOnly value={pushUrl} className="flex-1 px-4 py-3 bg-gray-100 rounded-lg text-sm" />
                  <button onClick={() => copyToClipboard(pushUrl, 'push')}
                    className="px-4 py-3 bg-blue-500 text-white rounded-lg">
                    {copied === 'push' ? <Check size={20} /> : <Copy size={20} />}
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">流密钥</label>
                <div className="flex gap-2">
                  <input readOnly value={streamKey} className="flex-1 px-4 py-3 bg-gray-100 rounded-lg text-sm" />
                  <button onClick={() => copyToClipboard(streamKey, 'key')}
                    className="px-4 py-3 bg-blue-500 text-white rounded-lg">
                    {copied === 'key' ? <Check size={20} /> : <Copy size={20} />}
                  </button>
                </div>
              </div>

              <div className="flex gap-3">
                <button onClick={() => navigate(`/live/${existingRoom.id}`)}
                  className="flex-1 py-3 bg-red-500 text-white rounded-lg hover:bg-red-600">
                  进入直播间
                </button>
                <button onClick={handleStopLive}
                  className="flex-1 py-3 bg-gray-500 text-white rounded-lg hover:bg-gray-600">
                  结束直播
                </button>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    );
  }

  // 等待获取 streamKey
  if (!userStreamKey) {
    return (
      <div className="min-h-[70vh] flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  // 创建直播间界面 - 横向撑满
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 py-12">
      <div className="max-w-7xl mx-auto px-4">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
          className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg p-8"
        >
          <div className="flex items-center gap-3 mb-8">
            <div className="w-12 h-12 bg-red-500 rounded-xl flex items-center justify-center">
              <Video className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold">开始直播</h1>
              <p className="text-gray-500">填写直播间信息后即可开播</p>
            </div>
          </div>

          {errorMsg && (
            <div className="mb-6 p-3 rounded-lg bg-red-50 text-red-600 text-sm">{errorMsg}</div>
          )}

          <div className="space-y-6">
            {/* 标题 */}
            <div>
              <label className="block text-sm font-medium mb-2">直播间标题 *</label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="直播间的标题..."
                className="w-full px-4 py-3 border rounded-lg focus:ring-2 focus:ring-red-500"
              />
            </div>

            {/* 简介 */}
            <div>
              <label className="block text-sm font-medium mb-2">简介</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                placeholder="介绍一下直播内容..."
                className="w-full px-4 py-3 border rounded-lg focus:ring-2 focus:ring-red-500 resize-none"
              />
            </div>

            {/* 直播封面 */}
            <div>
              <label className="block text-sm font-medium mb-2">直播封面</label>
              <div className="flex items-start gap-4">
                <div className="relative w-40 aspect-video bg-gray-100 rounded-lg overflow-hidden border">
                  {coverPreview ? (
                    <img src={coverPreview} alt="封面预览" className="w-full h-full object-cover" />
                  ) : coverUrl !== DEFAULT_COVER ? (
                    <img src={coverUrl} alt="封面" className="w-full h-full object-cover" />
                  ) : (
                    <div className="w-full h-full flex flex-col items-center justify-center text-gray-400">
                      <ImageIcon className="w-8 h-8 mb-1" />
                      <span className="text-xs">无封面</span>
                    </div>
                  )}
                </div>
                <div>
                  <input
                    ref={coverInputRef}
                    type="file"
                    accept="image/jpeg,image/png,image/jpg"
                    onChange={handleCoverUpload}
                    className="hidden"
                  />
                  <button
                    type="button"
                    onClick={() => coverInputRef.current?.click()}
                    disabled={isUploadingCover}
                    className="px-4 py-2 text-sm border rounded-lg hover:bg-gray-50 flex items-center gap-2"
                  >
                    {isUploadingCover ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      <ImageIcon className="w-4 h-4" />
                    )}
                    {isUploadingCover ? '上传中...' : '选择图片'}
                  </button>
                  {(coverPreview || coverUrl !== DEFAULT_COVER) && (
                    <button
                      type="button"
                      onClick={removeCover}
                      className="ml-2 px-4 py-2 text-sm border rounded-lg text-red-500 hover:bg-red-50"
                    >
                      <X className="w-4 h-4 inline mr-1" />
                      移除
                    </button>
                  )}
                  <p className="text-xs text-gray-500 mt-2">
                    建议尺寸 16:9，不超过2MB
                  </p>
                </div>
              </div>
            </div>

            {/* OBS 配置信息 */}
            <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
              <h3 className="font-medium mb-3">OBS 推流配置</h3>
              <div className="space-y-3">
                <div>
                  <label className="block text-xs text-gray-500 mb-1">推流地址</label>
                  <div className="flex gap-2">
                    <input readOnly value={`rtmp://${window.location.hostname}:1935/live`}
                      className="flex-1 px-3 py-2 bg-white dark:bg-gray-800 rounded text-sm" />
                    <button onClick={() => copyToClipboard(`rtmp://${window.location.hostname}:1935/live`, 'server')}
                      className="px-3 py-2 bg-blue-500 text-white rounded-lg text-sm">
                      {copied === 'server' ? <Check size={16} /> : <Copy size={16} />}
                    </button>
                  </div>
                </div>
                <div>
                  <label className="block text-xs text-gray-500 mb-1">串流密钥</label>
                  <div className="flex gap-2">
                    <input readOnly value={userStreamKey}
                      className="flex-1 px-3 py-2 bg-white dark:bg-gray-800 rounded text-sm" />
                    <button onClick={() => copyToClipboard(userStreamKey, 'key')}
                      className="px-3 py-2 bg-blue-500 text-white rounded-lg text-sm">
                      {copied === 'key' ? <Check size={16} /> : <Copy size={16} />}
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* 开始直播按钮 */}
            <button
              onClick={handleStart}
              disabled={!title.trim() || isLoading}
              className="w-full py-4 bg-red-500 hover:bg-red-600 disabled:bg-gray-400 text-white font-semibold rounded-lg flex items-center justify-center gap-2"
            >
              {isLoading && <Loader2 className="w-5 h-5 animate-spin" />}
              {isLoading ? '创建中...' : '开始直播'}
            </button>
          </div>
        </motion.div>
      </div>
    </div>
  );
}

export default LiveStartPage;
