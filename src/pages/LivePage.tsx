import React, { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import flvjs from 'flv.js';
import {
  Users,
  Send,
  Heart,
  Share2,
  Maximize,
  Volume2,
  VolumeX,
  Loader2,
  Radio,
  ArrowLeft,
  AlertCircle,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useLiveStore } from '../stores/liveStore';
import { useAuthStore } from '../stores/authStore';

const DEFAULT_AVATAR =
  'https://api.dicebear.com/7.x/avataaars/svg?seed=creator';

export function LivePage() {
  const { roomId } = useParams<{ roomId: string }>();
  const navigate = useNavigate();

  const videoRef = useRef<HTMLVideoElement>(null);
  const flvPlayerRef = useRef<any>(null);
  const chatRef = useRef<HTMLDivElement>(null);

  const [chatInput, setChatInput] = useState('');
  const [chatColor, setChatColor] = useState('#333333');
  const [isMuted, setIsMuted] = useState(false);
  const [showDanmaku, setShowDanmaku] = useState(true);
  const [danmakuList, setDanmakuList] = useState<
    { id: string; content: string; color: string; top: number }[]
  >([]);
  const [streamStatus, setStreamStatus] = useState<'loading' | 'live' | 'offline'>('loading');

  const {
    currentRoom,
    messages,
    onlineCount,
    isConnected,
    isLoading,
    fetchRoomDetail,
    connectWebSocket,
    disconnectWebSocket,
    sendDanmaku,
  } = useLiveStore();

  const { isLoggedIn, user, openLoginModal } = useAuthStore();

  // 获取直播间详情
  useEffect(() => {
    if (!roomId) return;
    fetchRoomDetail(roomId);
    connectWebSocket(roomId);

    return () => {
      disconnectWebSocket();
    };
  }, [roomId]);

  // 初始化 flv.js 播放器 - 简化版
  useEffect(() => {
    if (!currentRoom?.pullUrl || !videoRef.current) return;
    
    if (flvPlayerRef.current) {
      flvPlayerRef.current.destroy();
      flvPlayerRef.current = null;
    }
    
    const hostname = window.location.hostname;
    let flvUrl = currentRoom.pullUrl.replace('localhost', hostname);
    
    // 确保 URL 正确
    if (flvUrl.startsWith('http://localhost')) {
      flvUrl = flvUrl.replace('localhost', hostname);
    }
    
    console.log('播放地址:', flvUrl);
    
    if (flvjs.isSupported()) {
      try {
        const player = flvjs.createPlayer({
          type: 'flv',
          url: flvUrl,
          isLive: true,
        });
        player.attachMediaElement(videoRef.current);
        player.load();
        
        // 使用字符串事件名避免 TypeScript 错误
        player.on(flvjs.Events.ERROR, () => {
          console.error('播放器错误');
          setStreamStatus('offline');
        });
        
        // 播放
        const playPromise = player.play();
        if (playPromise !== undefined) {
          playPromise.then(() => {
            console.log('开始播放');
            setStreamStatus('live');
          }).catch((err: Error) => {
            console.warn('自动播放失败:', err);
            setStreamStatus('offline');
          });
        } else {
          setStreamStatus('live');
        }
        
        flvPlayerRef.current = player;
      } catch (err) {
        console.error('创建播放器失败:', err);
        setStreamStatus('offline');
      }
    } else {
      console.warn('flv.js 不支持');
      setStreamStatus('offline');
    }
    
    return () => {
      if (flvPlayerRef.current) {
        flvPlayerRef.current.destroy();
        flvPlayerRef.current = null;
      }
    };
  }, [currentRoom]);

  // 滚动到底部
  useEffect(() => {
    if (!chatRef.current) return;
    chatRef.current.scrollTop = chatRef.current.scrollHeight;
  }, [messages]);

  // 弹幕动画
  useEffect(() => {
    const danmakuMessages = messages.filter((message) => message.type === 'danmaku');
    if (danmakuMessages.length === 0) return;
    const latest = danmakuMessages[danmakuMessages.length - 1];
    const newDanmaku = {
      id: `${latest.id}-${Date.now()}`,
      content: latest.content,
      color: latest.color || '#333333',
      top: Math.random() * 60 + 10,
    };
    setDanmakuList((prev) => [...prev.slice(-20), newDanmaku]);
    const timer = window.setTimeout(() => {
      setDanmakuList((prev) => prev.filter((item) => item.id !== newDanmaku.id));
    }, 6000);
    return () => window.clearTimeout(timer);
  }, [messages]);

  const handleSendMessage = async () => {
    if (!chatInput.trim()) return;
    if (!isLoggedIn) {
      openLoginModal();
      return;
    }
    if (!currentRoom) return;
    
    const content = chatInput.trim();
    const color = chatColor;
    
    try {
      const auth = JSON.parse(localStorage.getItem('auth-storage')!);
      const token = auth.state?.token;
      
      const response = await fetch(`http://localhost:8000/api/live/${currentRoom.id}/danmaku`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          content: content,
          color: color,
          position: 0,
          videoTime: 0
        })
      });
      
      if (response.ok) {
        setChatInput('');
        // 不再本地添加消息，等待服务器通过 WebSocket 广播回来
      } else {
        console.error('发送失败');
      }
    } catch (error) {
      console.error('发送失败:', error);
    }
  };

  const toggleMute = () => {
    if (!videoRef.current) return;
    videoRef.current.muted = !videoRef.current.muted;
    setIsMuted(videoRef.current.muted);
  };

  const handleFullscreen = () => {
    const video = videoRef.current;
    if (!video) return;
    if (video.requestFullscreen) {
      video.requestFullscreen();
    }
  };

  const handleShare = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      alert('直播间链接已复制');
    } catch {
      alert('复制失败，请手动复制浏览器地址');
    }
  };

  if (isLoading && !currentRoom) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  if (!currentRoom) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-white">
        <div className="text-center bg-white rounded-2xl p-8 shadow-sm border">
          <Radio className="w-16 h-16 text-gray-400 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-gray-900 mb-2">
            直播间不存在
          </h2>
          <p className="text-gray-500 mb-6">
            请返回直播列表重新选择直播间。
          </p>
          <button
            onClick={() => navigate('/discover')}
            className="px-5 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            返回直播列表
          </button>
        </div>
      </div>
    );
  }

  const displayOnlineCount = Number(onlineCount || currentRoom.onlineCount || 0);

  return (
    <div className="min-h-screen bg-white">
      <div className="max-w-7xl mx-auto px-4 py-6">
        <button
          onClick={() => navigate(-1)}
          className="mb-4 inline-flex items-center gap-2 text-sm text-gray-500 hover:text-blue-600"
        >
          <ArrowLeft className="w-4 h-4" />
          返回
        </button>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-4">
            <div className="relative bg-gray-900 rounded-xl overflow-hidden aspect-video">
              {/* 视频播放器 */}
              <video
                ref={videoRef}
                className="w-full h-full object-contain"
                muted
                autoPlay
                playsInline
                poster={currentRoom.cover}
              />

              {/* 离线/无推流提示 */}
              {streamStatus === 'offline' && (
                <div className="absolute inset-0 bg-gradient-to-br from-gray-100 to-gray-200 flex flex-col items-center justify-center">
                  <AlertCircle className="w-16 h-16 text-gray-400 mb-4" />
                  <p className="text-gray-500 text-lg font-medium">当前直播没有内容</p>
                  <p className="text-gray-400 text-sm mt-2">主播可能暂时离开，请稍后再试</p>
                </div>
              )}

              {/* 加载中提示 */}
              {streamStatus === 'loading' && (
                <div className="absolute inset-0 bg-gray-900 flex flex-col items-center justify-center">
                  <Loader2 className="w-10 h-10 animate-spin text-gray-400 mb-3" />
                  <p className="text-gray-400">等待推流...</p>
                </div>
              )}

              {/* 弹幕层 - 只在直播时显示 */}
              {showDanmaku && streamStatus === 'live' && (
                <div className="absolute inset-0 pointer-events-none overflow-hidden">
                  <AnimatePresence>
                    {danmakuList.map((item) => (
                      <motion.div
                        key={item.id}
                        initial={{ x: '100vw', opacity: 1 }}
                        animate={{ x: '-100%' }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 6, ease: 'linear' }}
                        className="absolute text-xl md:text-2xl font-bold whitespace-nowrap drop-shadow-md"
                        style={{
                          color: item.color,
                          top: `${item.top}%`,
                          textShadow: '1px 1px 2px rgba(0,0,0,0.5)',
                        }}
                      >
                        {item.content}
                      </motion.div>
                    ))}
                  </AnimatePresence>
                </div>
              )}

              {/* 顶部信息栏 */}
              <div className="absolute top-4 left-4 flex items-center gap-2">
                <span className={`px-3 py-1 text-white text-sm font-bold rounded-full ${streamStatus === 'live' ? 'bg-red-500 animate-pulse' : 'bg-gray-500'}`}>
                  {streamStatus === 'live' ? 'LIVE' : '离线'}
                </span>

                <span className="px-3 py-1 bg-black/50 text-white text-sm rounded-full flex items-center gap-1">
                  <Users className="w-4 h-4" />
                  {displayOnlineCount}
                </span>

                <span className={`px-3 py-1 text-sm rounded-full ${isConnected ? 'bg-green-500/90 text-white' : 'bg-black/50 text-white'}`}>
                  {isConnected ? '聊天已连接' : '聊天连接中'}
                </span>
              </div>

              {/* 底部控制栏 */}
              <div className="absolute bottom-4 right-4 flex items-center gap-2">
                <button
                  onClick={toggleMute}
                  className="p-2 bg-black/50 text-white rounded-full hover:bg-black/70 transition-colors"
                >
                  {isMuted ? <VolumeX className="w-5 h-5" /> : <Volume2 className="w-5 h-5" />}
                </button>

                <button
                  onClick={() => setShowDanmaku((prev) => !prev)}
                  className={`px-3 py-2 rounded-full text-sm font-medium transition-colors ${showDanmaku ? 'bg-blue-500 text-white' : 'bg-black/50 text-white'}`}
                >
                  弹幕
                </button>

                <button
                  onClick={handleFullscreen}
                  className="p-2 bg-black/50 text-white rounded-full hover:bg-black/70 transition-colors"
                >
                  <Maximize className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* 直播间信息 */}
            <div className="bg-white rounded-xl p-6 shadow-sm border">
              <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
                <div className="flex gap-4">
                  <img
                    src={currentRoom.anchorAvatar || DEFAULT_AVATAR}
                    alt={currentRoom.anchorName}
                    className="w-14 h-14 rounded-full object-cover bg-gray-200"
                    onError={(e) => {
                      e.currentTarget.src = DEFAULT_AVATAR;
                    }}
                  />

                  <div>
                    <h1 className="text-xl font-bold text-gray-900">
                      {currentRoom.title}
                    </h1>

                    <div className="flex items-center gap-3 mt-1 text-sm text-gray-500">
                      <span>{currentRoom.anchorName}</span>
                      <span className="px-2 py-0.5 bg-gray-100 rounded-full">
                        {currentRoom.categoryName}
                      </span>
                    </div>

                    {currentRoom.description && (
                      <p className="text-sm text-gray-500 mt-2">
                        {currentRoom.description}
                      </p>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <button className="flex items-center gap-2 px-4 py-2 bg-red-500 text-white rounded-full hover:bg-red-600 transition-colors">
                    <Heart className="w-4 h-4" />
                    关注
                  </button>

                  <button
                    onClick={handleShare}
                    className="p-2 bg-gray-100 rounded-full hover:bg-gray-200 transition-colors"
                  >
                    <Share2 className="w-5 h-5 text-gray-600" />
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* 聊天室 */}
          <div className="bg-white rounded-xl shadow-sm border overflow-hidden">
            <div className="p-4 border-b bg-gray-50 flex items-center justify-between">
              <h3 className="font-semibold text-gray-900">直播间聊天</h3>
              <div className="flex items-center gap-1 text-sm text-gray-500">
                <Users className="w-4 h-4" />
                {displayOnlineCount}
              </div>
            </div>

            <div ref={chatRef} className="h-96 overflow-y-auto p-4 space-y-3 scrollbar-thin bg-gray-50">
              {messages.length === 0 && (
                <div className="text-center text-gray-400 py-20 text-sm">
                  暂无消息，快来互动吧~
                </div>
              )}
              {(() => {
                // 记录已显示的进入消息
                const seenEntries = new Set<string>();
                const filteredMessages = messages.filter(msg => {
                  if (msg.type === 'system' && msg.content.includes('进入直播间')) {
                    const key = `${msg.content}-${msg.timestamp?.slice(0, 16)}`;
                    if (seenEntries.has(key)) return false;
                    seenEntries.add(key);
                    return true;
                  }
                  return true;
                });
                return filteredMessages.map((msg) => (
                  <div key={msg.id}>
                    {msg.type === 'system' && (
                      <div className="text-center">
                        <span className="inline-block px-3 py-1 text-xs text-gray-400 bg-gray-100 rounded-full">
                          {msg.content}
                        </span>
                      </div>
                    )}
                    {msg.type === 'danmaku' && (
                      <div className="flex items-start gap-2.5">
                        <div className="flex-shrink-0">
                          <img
                            src={msg.userAvatar || `https://api.dicebear.com/7.x/avataaars/svg?seed=${msg.username || 'user'}`}
                            alt={msg.username}
                            className="w-8 h-8 rounded-full object-cover"
                            onError={(e) => {
                              e.currentTarget.src = `https://api.dicebear.com/7.x/avataaars/svg?seed=${msg.username || 'user'}`;
                            }}
                          />
                        </div>
                        <div className="flex-1">
                          <div className="flex items-baseline gap-2">
                            <span className="text-sm font-semibold text-gray-800">
                              {msg.username || '观众'}
                            </span>
                            <span className="text-xs text-gray-400">
                              {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </span>
                          </div>
                          <p className="text-sm text-gray-700 mt-0.5 break-words">
                            {msg.content}
                          </p>
                        </div>
                      </div>
                    )}
                  </div>
                ));
              })()}
            </div>

            <div className="p-4 border-t bg-white">
              {isLoggedIn ? (
                <div className="space-y-3">
                  <div className="flex gap-2">
                    {['#FFFFFF', '#333333', '#FF6B6B', '#4ECDC4', '#FFE66D', '#95E1D3'].map((color) => (
                      <button
                        key={color}
                        onClick={() => setChatColor(color)}
                        className={`w-6 h-6 rounded-full transition-transform hover:scale-110 ${
                          chatColor === color ? 'ring-2 ring-offset-1 ring-gray-400' : ''
                        }`}
                        style={{ backgroundColor: color }}
                      />
                    ))}
                  </div>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={chatInput}
                      onChange={(e) => setChatInput(e.target.value)}
                      placeholder="说点什么..."
                      className="flex-1 px-4 py-2.5 bg-gray-100 rounded-full border-0 focus:ring-2 focus:ring-blue-500 text-sm text-gray-900 outline-none"
                      onKeyDown={(e) => { if (e.key === 'Enter') handleSendMessage(); }}
                    />
                    <button
                      onClick={handleSendMessage}
                      disabled={!chatInput.trim()}
                      className="px-5 py-2.5 bg-blue-500 text-white rounded-full hover:bg-blue-600 disabled:opacity-50 transition-colors flex items-center gap-1"
                    >
                      <Send className="w-4 h-4" />
                      发送
                    </button>
                  </div>
                </div>
              ) : (
                <div className="text-center py-4">
                  <p className="text-sm text-gray-500 mb-3">登录后参与聊天</p>
                  <button onClick={openLoginModal} className="px-5 py-2 bg-blue-600 text-white rounded-full hover:bg-blue-700 text-sm">
                    去登录
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default LivePage;