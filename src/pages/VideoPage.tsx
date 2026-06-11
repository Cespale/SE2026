import React, { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { FollowButton } from '../components/social/FollowButton';
import {
  Play,
  Pause,
  Volume2,
  VolumeX,
  Maximize,
  Heart,
  Share2,
  MessageCircle,
  Send,
  Loader2,
  Flag,
  Trash2,
} from 'lucide-react';
import { motion } from 'framer-motion';
import { useVideoStore, Danmaku } from '../stores/videoStore';
import { useAuthStore } from '../stores/authStore';
import { ReportModal } from '../components/ReportModal';
import { apiRequest } from '../api';

const DEFAULT_VIDEO_URL = '/demo-videos/This-is-beihang.mp4';
const BACKUP_VIDEO_URL = '/demo-videos/beihang2025.mp4';
const DEFAULT_COVER_URL =
  'https://images.unsplash.com/photo-1611162616475-46b635cb6868?w=900&auto=format&fit=crop';

function getPlayableVideoUrl(url?: string) {
  if (!url) return DEFAULT_VIDEO_URL;

  const cleanUrl = String(url).trim();
  if (!cleanUrl) return DEFAULT_VIDEO_URL;

  // 如果是上传的视频，添加后端地址前缀
  if (cleanUrl.startsWith('/uploads/')) {
    return `http://localhost:8000${cleanUrl}`;
  }

  const lower = cleanUrl.toLowerCase();
  if (
    lower.endsWith('.mp4') ||
    lower.endsWith('.webm') ||
    lower.endsWith('.ogg') ||
    lower.includes('.mp4?') ||
    lower.includes('.webm?') ||
    lower.includes('.ogg?')
  ) {
    return cleanUrl;
  }

  return DEFAULT_VIDEO_URL;
}

function formatTime(seconds: number) {
  if (!Number.isFinite(seconds) || seconds < 0) return '0:00';

  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);

  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export function VideoPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const videoRef = useRef<HTMLVideoElement>(null);
  const danmakuRef = useRef<HTMLDivElement>(null);

  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [showDanmaku, setShowDanmaku] = useState(true);
  const [danmakuInput, setDanmakuInput] = useState('');
  const [danmakuColor, setDanmakuColor] = useState('#FFFFFF');
  const [commentInput, setCommentInput] = useState('');
  const [replyTo, setReplyTo] = useState<{
    parentId: string;
    replyToUserId: string;
    replyToUsername: string;
  } | null>(null);
  const [expandedReplies, setExpandedReplies] = useState<Record<string, boolean>>({});
  const [activeDanmaku, setActiveDanmaku] = useState<Danmaku[]>([]);
  const [videoErrorText, setVideoErrorText] = useState('');

  const [isLiked, setIsLiked] = useState(false);
  const [localLikeCount, setLocalLikeCount] = useState(0);
  const [isLikeLoading, setIsLikeLoading] = useState(false);
  const [rejectReason, setRejectReason] = useState('');

  // 举报相关状态
  const [showReportModal, setShowReportModal] = useState(false);
  const [showCommentReportModal, setShowCommentReportModal] = useState(false);
  const [reportCommentId, setReportCommentId] = useState<string | null>(null);

  const {
    currentVideo,
    comments,
    danmakuList,
    relatedVideos,
    isLoading,
    fetchVideoDetail,
    fetchComments,
    fetchDanmaku,
    fetchRelatedVideos,
    addComment,
    sendDanmaku,
  } = useVideoStore();

  const { isLoggedIn, user, openLoginModal } = useAuthStore();

  // 点赞/取消点赞处理函数
  const handleLike = async () => {
    if (!isLoggedIn) {
      openLoginModal();
      return;
    }
    
    if (isLikeLoading) return;
    setIsLikeLoading(true);
    
    try {
      const token = localStorage.getItem('auth-storage') 
        ? JSON.parse(localStorage.getItem('auth-storage')!).state?.token 
        : '';
      
      if (isLiked) {
        const response = await fetch(`http://localhost:8000/api/videos/${id}/like`, {
          method: 'DELETE',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        });
        const data = await response.json();
        if (response.ok) {
          setIsLiked(false);
          setLocalLikeCount(data.data.likeCount);
        } else {
          console.error('取消点赞失败:', data);
        }
      } else {
        const response = await fetch(`http://localhost:8000/api/videos/${id}/like`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        });
        const data = await response.json();
        if (response.ok) {
          setIsLiked(true);
          setLocalLikeCount(data.data.likeCount);
        } else if (response.status === 400 && data.detail === '已经点过赞了') {
          setIsLiked(true);
          await fetchLikeStatus();
        } else {
          console.error('点赞失败:', data);
        }
      }
    } catch (error) {
      console.error('点赞请求失败:', error);
    } finally {
      setIsLikeLoading(false);
    }
  };

  useEffect(() => {
    if (!id) return;

    fetchVideoDetail(id);
    fetchComments(id);
    fetchDanmaku(id);
    fetchRelatedVideos(id);
    fetchLikeStatus();

    setCurrentTime(0);
    setDuration(0);
    setIsPlaying(false);
    setActiveDanmaku([]);
    setVideoErrorText('');
  }, [id]);

  useEffect(() => {
    if (currentVideo) {
      setLocalLikeCount(currentVideo.likeCount);
      if (currentVideo.auditStatus === 2) {
        setRejectReason(currentVideo.rejectReason || '未填写具体原因');
      }
    }
  }, [currentVideo]);

  const fetchLikeStatus = async () => {
    if (!id || !isLoggedIn) return;
    
    try {
      const response = await fetch(`http://localhost:8000/api/videos/${id}/like-status`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth-storage') ? JSON.parse(localStorage.getItem('auth-storage')!).state?.token : ''}`
        }
      });
      const data = await response.json();
      setIsLiked(data.isLiked);
    } catch (error) {
      console.error('获取点赞状态失败:', error);
    }
  };

  const safeVideoUrl = getPlayableVideoUrl(currentVideo?.videoUrl);
  const safePosterUrl = currentVideo?.coverUrl || DEFAULT_COVER_URL;

  const visibleComments = comments || [];

  const visibleDanmaku = danmakuList && danmakuList.length > 0 ? danmakuList : [];

  useEffect(() => {
    const current = currentTime;
    
    const newDanmaku = visibleDanmaku.filter((item) => {
      const itemTime = item.videoTime || 0;
      const alreadyActive = activeDanmaku.some(
        (active) => active.id === item.id
      );
      return Math.abs(itemTime - current) < 0.3 && !alreadyActive;
    });

    if (newDanmaku.length === 0) return;

    setActiveDanmaku((prev) => [...prev, ...newDanmaku]);

    const timer = setTimeout(() => {
      setActiveDanmaku((prev) =>
        prev.filter((item) => !newDanmaku.some((newItem) => newItem.id === item.id))
      );
    }, Math.max(...newDanmaku.map(item => item.content.length / 10 + 2.5)) * 1000 + 500);

    return () => clearTimeout(timer);
  }, [currentTime, visibleDanmaku]);

  const togglePlay = async () => {
    const video = videoRef.current;
    if (!video) return;

    try {
      if (video.paused) {
        await video.play();
        setIsPlaying(true);
      } else {
        video.pause();
        setIsPlaying(false);
      }
    } catch (error) {
      console.warn('播放被浏览器中断，用户再次点击即可播放:', error);
      setVideoErrorText('浏览器阻止了自动播放，请再次点击播放按钮。');
    }
  };

  const toggleMute = () => {
    const video = videoRef.current;
    if (!video) return;

    video.muted = !video.muted;
    setIsMuted(video.muted);
  };

  const handleTimeUpdate = () => {
    const video = videoRef.current;
    if (!video) return;

    setCurrentTime(video.currentTime);
    setDuration(Number.isFinite(video.duration) ? video.duration : 0);
  };

  const handleLoadedMetadata = () => {
    const video = videoRef.current;
    if (!video) return;

    setDuration(Number.isFinite(video.duration) ? video.duration : 0);
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const time = Number(e.target.value);
    const video = videoRef.current;

    if (!video) return;

    video.currentTime = time;
    setCurrentTime(time);
  };

  const handleSendDanmaku = async () => {
    if (!id || !danmakuInput.trim()) return;

    if (!isLoggedIn) {
      openLoginModal();
      return;
    }

    const videoTime = Math.floor(
      videoRef.current?.currentTime || currentTime || 0
    );

    await sendDanmaku(id, danmakuInput.trim(), danmakuColor, videoTime);
    await fetchDanmaku(id);

    setDanmakuInput('');
  };

  const handleSendComment = async () => {
    if (!id || !commentInput.trim()) return;

    if (!isLoggedIn) {
      openLoginModal();
      return;
    }

    await addComment(
      id,
      commentInput.trim(),
      replyTo?.parentId || '0',
      replyTo?.replyToUserId || ''
    );
    setCommentInput('');
    if (replyTo) {
      setExpandedReplies((s) => ({ ...s, [replyTo.parentId]: true }));
      setReplyTo(null);
    }
  };

  const startReply = (parentId: string, userId: string, username: string) => {
    if (!isLoggedIn) {
      openLoginModal();
      return;
    }
    setReplyTo({ parentId, replyToUserId: userId, replyToUsername: username });
    setTimeout(() => {
      document.getElementById('comment-input-anchor')?.scrollIntoView({ behavior: 'smooth' });
    }, 50);
  };

  const toggleReplies = async (commentId: string) => {
    const isOpen = !!expandedReplies[commentId];
    if (!isOpen) {
      const c = visibleComments.find((x) => x.id === commentId);
      if (c && (!c.replies || c.replies.length === 0) && (c.replyCount || 0) > 0) {
        await useVideoStore.getState().fetchReplies(commentId);
      }
    }
    setExpandedReplies((s) => ({ ...s, [commentId]: !isOpen }));
  };

  const renderContent = (text: string) => {
    const parts = text.split(/(@[\w一-龥]+)/g);
    return parts.map((p, i) =>
      p.startsWith('@') ? (
        <span key={i} className="text-blue-500">
          {p}
        </span>
      ) : (
        <span key={i}>{p}</span>
      )
    );
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
      alert('视频链接已复制');
    } catch {
      alert('复制失败，请手动复制浏览器地址');
    }
  };

  const handleVideoError = (e: React.SyntheticEvent<HTMLVideoElement>) => {
    const target = e.currentTarget;

    console.warn('视频加载失败，当前地址:', target.src);

    if (!target.src.includes(DEFAULT_VIDEO_URL)) {
      target.src = DEFAULT_VIDEO_URL;
      target.load();
      setVideoErrorText('原视频加载失败，已自动切换到备用演示视频。');
      return;
    }

    if (!target.src.includes(BACKUP_VIDEO_URL)) {
      target.src = BACKUP_VIDEO_URL;
      target.load();
      setVideoErrorText('默认视频加载失败，已切换到第二备用视频。');
      return;
    }

    setVideoErrorText('视频加载失败，请检查 public/demo-videos 里的文件是否存在。');
  };

  const showComments = currentVideo?.auditStatus === 1;
  const isPending = currentVideo?.auditStatus === 0;
  const isRejected = currentVideo?.auditStatus === 2;

  // 判断当前用户是否有权限删除评论
  const canDeleteComment = (commentUserId: string) => {
    if (!isLoggedIn) return false;
    // 管理员可以删除任何评论
    if (user?.userType === 2) return true;
    // 评论作者可以删除自己的评论
    if (user?.id === commentUserId) return true;
    // 视频创作者可以删除自己视频下的评论
    if (currentVideo?.uploaderId === user?.id) return true;
    return false;
  };

  // 删除评论
  const handleDeleteComment = async (commentId: string) => {
    if (!confirm('确定要删除这条评论吗？')) return;
    try {
      await apiRequest(`/api/comments/${commentId}`, { method: 'DELETE' });
      // 刷新评论列表
      await fetchComments(id!);
    } catch (error) {
      console.error('删除评论失败:', error);
      alert('删除失败');
    }
  };

  if (isLoading && !currentVideo) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
        <div className="text-center">
          <Loader2 className="w-12 h-12 animate-spin text-blue-500 mx-auto mb-4" />
          <p className="text-gray-500">正在加载视频...</p>
        </div>
      </div>
    );
  }

  if (!currentVideo) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
        <div className="text-center">
          <p className="text-gray-500 mb-4">
            视频加载失败，请返回首页重新选择视频。
          </p>
          <button
            onClick={() => navigate('/')}
            className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
          >
            返回首页
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          <div className="relative bg-black rounded-xl overflow-hidden aspect-video group">
            <video
              key={`${currentVideo.id}-${safeVideoUrl}`}
              ref={videoRef}
              className="w-full h-full bg-black object-contain"
              src={safeVideoUrl}
              poster={safePosterUrl}
              preload="metadata"
              playsInline
              onClick={togglePlay}
              onTimeUpdate={handleTimeUpdate}
              onLoadedMetadata={handleLoadedMetadata}
              onPlay={() => setIsPlaying(true)}
              onPause={() => setIsPlaying(false)}
              onEnded={() => setIsPlaying(false)}
              onError={handleVideoError}
            >
              当前浏览器不支持视频播放。
            </video>

            {!isPlaying && (
              <button
                onClick={togglePlay}
                className="absolute inset-0 flex items-center justify-center bg-black/10 hover:bg-black/20 transition-colors"
              >
                <div className="w-16 h-16 rounded-full bg-white/90 flex items-center justify-center shadow-lg">
                  <Play
                    className="w-8 h-8 text-gray-900 ml-1"
                    fill="currentColor"
                  />
                </div>
              </button>
            )}

            {showDanmaku && (
              <div ref={danmakuRef} className="absolute inset-0 pointer-events-none overflow-hidden">
                {activeDanmaku.map((item, index) => {
                  const topPosition = 10 + (index % 7) * 10;
                  const duration = Math.max(3, Math.min(6, item.content.length / 10 + 2.5));
                  
                  return (
                    <motion.div
                      key={item.id}
                      initial={{ x: '100vw' }}
                      animate={{ x: '-100%' }}
                      transition={{ duration, ease: 'linear' }}
                      className="absolute text-base md:text-lg font-medium whitespace-nowrap"
                      style={{
                        color: item.color || '#ffffff',
                        top: `${topPosition}%`,
                        textShadow: '1px 1px 2px rgba(0,0,0,0.85)',
                      }}
                    >
                      {item.content}
                    </motion.div>
                  );
                })}
              </div>
            )}

            {videoErrorText && (
              <div className="absolute top-3 left-3 right-3 px-3 py-2 rounded-lg bg-red-500/90 text-white text-sm">
                {videoErrorText}
              </div>
            )}

            <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/90 to-transparent p-4 opacity-100 md:opacity-0 md:group-hover:opacity-100 transition-opacity">
              <div className="flex items-center gap-4">
                <button
                  onClick={togglePlay}
                  className="text-white hover:text-blue-400"
                >
                  {isPlaying ? <Pause size={24} /> : <Play size={24} />}
                </button>

                <button
                  onClick={toggleMute}
                  className="text-white hover:text-blue-400"
                >
                  {isMuted ? <VolumeX size={24} /> : <Volume2 size={24} />}
                </button>

                <input
                  type="range"
                  min="0"
                  max={duration || 0}
                  value={Math.min(currentTime, duration || 0)}
                  onChange={handleSeek}
                  className="flex-1 h-1 bg-white/30 rounded-full appearance-none cursor-pointer"
                />

                <span className="text-white text-sm min-w-[92px] text-right">
                  {formatTime(currentTime)} / {formatTime(duration)}
                </span>

                <button
                  onClick={handleFullscreen}
                  className="text-white hover:text-blue-400"
                >
                  <Maximize size={24} />
                </button>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 bg-gray-100 dark:bg-gray-800 p-3 rounded-lg">
            <input
              type="text"
              value={danmakuInput}
              onChange={(e) => setDanmakuInput(e.target.value)}
              placeholder="发弹幕..."
              className="flex-1 px-4 py-2 bg-white dark:bg-gray-700 rounded-lg border-0 focus:ring-2 focus:ring-blue-500 text-gray-900 dark:text-white"
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  handleSendDanmaku();
                }
              }}
            />

            <div className="hidden sm:flex gap-1">
              {['#FFFFFF', '#FF6B6B', '#4ECDC4', '#FFE66D', '#95E1D3'].map(
                (color) => (
                  <button
                    key={color}
                    onClick={() => setDanmakuColor(color)}
                    className={`w-6 h-6 rounded-full border-2 ${
                      danmakuColor === color
                        ? 'border-gray-800 dark:border-white'
                        : 'border-transparent'
                    }`}
                    style={{ backgroundColor: color }}
                  />
                )
              )}
            </div>

            <button
              onClick={handleSendDanmaku}
              className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
            >
              发送
            </button>

            <button
              onClick={() => setShowDanmaku(!showDanmaku)}
              className={`px-3 py-2 rounded-lg transition-colors ${
                showDanmaku
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-200 text-gray-700'
              }`}
            >
              弹幕
            </button>
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm">
            <h1 className="text-xl font-bold mb-2 text-gray-900 dark:text-white">
              {currentVideo.title}
            </h1>

            <div className="flex flex-wrap items-center gap-4 text-sm text-gray-500 mb-4">
              <span>{currentVideo.viewCount.toLocaleString()} 次观看</span>
              <span>
                {new Date(currentVideo.uploadTime).toLocaleDateString()}
              </span>

              <div className="flex flex-wrap gap-2">
                {currentVideo.categoryName && (
                  <span className="px-2 py-1 bg-blue-100 dark:bg-blue-800 text-blue-700 dark:text-blue-200 rounded-full text-xs">
                    {currentVideo.categoryName}
                  </span>
                )}
              </div>
            </div>

            <p className="text-gray-600 dark:text-gray-300">
              {currentVideo.description}
            </p>

            <div className="flex flex-wrap items-center gap-4 mt-4 pt-4 border-t border-gray-100 dark:border-gray-700">
              <button
                onClick={handleLike}
                disabled={isLikeLoading}
                className={`flex items-center gap-2 px-4 py-2 rounded-full transition-colors ${
                  isLiked
                    ? 'bg-red-500 text-white hover:bg-red-600'
                    : 'bg-gray-100 dark:bg-gray-700 hover:bg-red-50 hover:text-red-500'
                }`}
              >
                <Heart size={20} fill={isLiked ? 'currentColor' : 'none'} />
                <span>{(localLikeCount || currentVideo.likeCount).toLocaleString()}</span>
              </button>

              <button
                onClick={handleShare}
                className="flex items-center gap-2 px-4 py-2 bg-gray-100 dark:bg-gray-700 rounded-full hover:bg-blue-50 hover:text-blue-500 transition-colors"
              >
                <Share2 size={20} />
                <span>分享</span>
              </button>

              <button
                onClick={() => setShowReportModal(true)}
                className="flex items-center gap-2 px-4 py-2 bg-gray-100 dark:bg-gray-700 rounded-full hover:bg-red-50 hover:text-red-500 transition-colors"
              >
                <Flag size={20} />
                <span>举报</span>
              </button>
            </div>
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm">
            <div className="flex items-center gap-4">
              <Link to={`/user/${currentVideo.uploaderId}`}>
                <img
                  src={currentVideo.uploaderAvatar}
                  alt={currentVideo.uploaderName}
                  className="w-12 h-12 rounded-full hover:opacity-80 transition-opacity"
                />
              </Link>

              <div className="flex-1">
                <Link
                  to={`/user/${currentVideo.uploaderId}`}
                  className="font-semibold text-gray-900 dark:text-white hover:text-blue-500 transition-colors"
                >
                  {currentVideo.uploaderName}
                </Link>
                <p className="text-sm text-gray-500">视频创作者</p>
              </div>

              <FollowButton userId={currentVideo.uploaderId} />
            </div>
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm">
            <h3 className="text-lg font-bold mb-4 flex items-center gap-2 text-gray-900 dark:text-white">
              <MessageCircle size={20} />
              评论 ({visibleComments.length})
            </h3>

            {isPending && (
              <div className="text-center py-8 text-gray-500">
                <p>视频审核中，暂不开放评论</p>
              </div>
            )}

            {isRejected && (
              <div>
                <div className="bg-red-50 dark:bg-red-900/20 rounded-lg p-4 mb-4">
                  <p className="text-red-600 text-sm font-medium mb-1">审核未通过</p>
                  <p className="text-red-700 dark:text-red-300 text-sm">
                    理由：{rejectReason}
                  </p>
                </div>
                <div className="text-center py-8 text-gray-500">
                  <p>视频未通过审核，暂不开放评论</p>
                </div>
              </div>
            )}

            {showComments && (
              <>
                {isLoggedIn ? (
                  <div id="comment-input-anchor" className="flex flex-col gap-2 mb-6">
                    {replyTo && (
                      <div className="flex items-center justify-between bg-blue-50 dark:bg-blue-900/30 text-sm px-3 py-2 rounded-lg">
                        <span className="text-blue-600 dark:text-blue-400">
                          回复 <strong>@{replyTo.replyToUsername}</strong>
                        </span>
                        <button onClick={() => setReplyTo(null)} className="text-gray-500 hover:text-red-500">取消</button>
                      </div>
                    )}
                    <div className="flex gap-3">
                      <img
                        src={
                          user?.avatar ||
                          'https://api.dicebear.com/7.x/avataaars/svg?seed=user'
                        }
                        alt={user?.nickname || '用户'}
                        className="w-10 h-10 rounded-full"
                      />

                      <div className="flex-1 flex gap-2">
                        <input
                          type="text"
                          value={commentInput}
                          onChange={(e) => setCommentInput(e.target.value)}
                          placeholder={replyTo ? `回复 @${replyTo.replyToUsername}...` : '写下你的评论(支持 @用户名)...'}
                          className="flex-1 px-4 py-2 bg-gray-100 dark:bg-gray-700 rounded-lg border-0 focus:ring-2 focus:ring-blue-500 text-gray-900 dark:text-white"
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') {
                              handleSendComment();
                            }
                          }}
                        />

                        <button
                          onClick={handleSendComment}
                          className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
                        >
                          <Send size={18} />
                        </button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="mb-6 p-4 rounded-lg bg-gray-100 dark:bg-gray-700 text-sm text-gray-500 flex items-center justify-between">
                    <span>登录后可以发表评论。</span>
                    <button
                      onClick={openLoginModal}
                      className="px-3 py-1.5 bg-blue-500 text-white rounded-lg"
                    >
                      去登录
                    </button>
                  </div>
                )}

                <div className="space-y-4">
                  {visibleComments.map((comment) => (
                    <div key={comment.id} className="flex gap-3">
                      <img
                        src={comment.userAvatar}
                        alt={comment.username}
                        className="w-10 h-10 rounded-full"
                      />

                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-gray-900 dark:text-white">
                            {comment.username}
                          </span>
                          {comment.isTop && (
                            <span className="px-2 py-0.5 bg-red-100 text-red-600 text-xs rounded">
                              置顶
                            </span>
                          )}
                        </div>

                        <p className="text-gray-700 dark:text-gray-300 mt-1">
                          {renderContent(comment.content)}
                        </p>

                        <div className="flex items-center gap-4 mt-2 text-sm text-gray-500">
                          <span>
                            {new Date(comment.createTime).toLocaleDateString()}
                          </span>

                          

                          <button
                            onClick={() => startReply(comment.id, comment.userId, comment.username)}
                            className="hover:text-blue-500"
                          >
                            回复
                          </button>

                          <button
                            onClick={() => {
                              setReportCommentId(comment.id);
                              setShowCommentReportModal(true);
                            }}
                            className="hover:text-red-500"
                          >
                            <Flag size={14} />
                          </button>

                          {canDeleteComment(comment.userId) && (
                            <button
                              onClick={() => handleDeleteComment(comment.id)}
                              className="hover:text-red-500"
                            >
                              <Trash2 size={14} />
                            </button>
                          )}

                          {(comment.replyCount || 0) > 0 && (
                            <button
                              onClick={() => toggleReplies(comment.id)}
                              className="hover:text-blue-500"
                            >
                              {expandedReplies[comment.id] ? '收起回复' : `查看 ${comment.replyCount} 条回复`}
                            </button>
                          )}
                        </div>

                        {expandedReplies[comment.id] && comment.replies && comment.replies.length > 0 && (
                          <div className="mt-3 pl-4 border-l-2 border-gray-200 dark:border-gray-700 space-y-3">
                            {comment.replies.map((reply) => (
                              <div key={reply.id} className="flex gap-2">
                                <img
                                  src={reply.userAvatar}
                                  alt={reply.username}
                                  className="w-8 h-8 rounded-full"
                                />

                                <div className="flex-1">
                                  <div className="text-sm">
                                    <span className="font-medium text-gray-900 dark:text-white">
                                      {reply.username}
                                    </span>
                                    {reply.replyToUsername && (
                                      <span className="text-gray-500">
                                        {' '}回复{' '}
                                        <span className="text-blue-500">@{reply.replyToUsername}</span>
                                      </span>
                                    )}
                                  </div>
                                  <p className="text-gray-700 dark:text-gray-300 text-sm">
                                    {renderContent(reply.content)}
                                  </p>
                                  <button
                                    onClick={() => startReply(comment.id, reply.userId, reply.username)}
                                    className="text-xs text-gray-500 hover:text-blue-500 mt-1"
                                  >
                                    回复
                                  </button>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>

        <div className="space-y-4">
          <h3 className="font-bold text-lg text-gray-900 dark:text-white">
            相关推荐
          </h3>

          {relatedVideos.length === 0 && (
            <div className="text-sm text-gray-500 bg-white dark:bg-gray-800 rounded-lg p-4">
              暂无相关推荐
            </div>
          )}

          {relatedVideos.map((video) => (
            <div
              key={video.id}
              onClick={() => navigate(`/video/${video.id}`)}
              className="flex gap-3 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800 p-2 rounded-lg transition-colors"
            >
              <div className="relative w-40 aspect-video rounded-lg overflow-hidden bg-gray-200">
                <img
                  src={video.coverUrl || DEFAULT_COVER_URL}
                  alt={video.title}
                  className="w-full h-full object-cover"
                  loading="lazy"
                  onError={(e) => {
                    e.currentTarget.src = DEFAULT_COVER_URL;
                  }}
                />

                <span className="absolute bottom-1 right-1 px-1.5 py-0.5 bg-black/70 text-white text-xs rounded">
                  {formatTime(video.duration)}
                </span>
              </div>

              <div className="flex-1">
                <h4 className="font-medium text-sm line-clamp-2 text-gray-900 dark:text-white">
                  {video.title}
                </h4>
                <p className="text-xs text-gray-500 mt-1">
                  {video.uploaderName}
                </p>
                <p className="text-xs text-gray-500">
                  {video.viewCount.toLocaleString()} 次观看
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 举报弹窗 */}
      <ReportModal
        isOpen={showReportModal}
        onClose={() => setShowReportModal(false)}
        targetType={0}
        targetId={id!}
      />
      <ReportModal
        isOpen={showCommentReportModal}
        onClose={() => {
          setShowCommentReportModal(false);
          setReportCommentId(null);
        }}
        targetType={1}
        targetId={reportCommentId || ''}
      />
    </div>
  );
}

export default VideoPage;