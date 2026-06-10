import React, { useEffect, useCallback, useState } from 'react';
import { motion } from 'framer-motion';
import { useNavigate, Link } from 'react-router-dom';
import { useVideoStore } from '../stores/videoStore';
import { useAuthStore } from '../stores/authStore';
import { Users, Loader2, Eye, Heart, MessageCircle, Calendar } from 'lucide-react';

export function SubscriptionPage() {
  const navigate = useNavigate();
  const { isLoggedIn } = useAuthStore();
  const {
    videos,
    isLoading,
    hasMore,
    fetchFeed,
  } = useVideoStore();

  const [page, setPage] = useState(1);

  useEffect(() => {
    if (!isLoggedIn) return;
    fetchFeed(1);
    setPage(1);
  }, [fetchFeed, isLoggedIn]);

  const handleScroll = useCallback(() => {
    const nearBottom =
      window.innerHeight + window.scrollY >= document.body.offsetHeight - 120;

    if (nearBottom && hasMore && !isLoading) {
      const nextPage = page + 1;
      fetchFeed(nextPage);
      setPage(nextPage);
    }
  }, [hasMore, isLoading, fetchFeed, page]);

  useEffect(() => {
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, [handleScroll]);

  function formatDate(dateStr: string) {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    
    if (diffMins < 1) return '刚刚';
    if (diffMins < 60) return `${diffMins}分钟前`;
    if (diffHours < 24) return `${diffHours}小时前`;
    if (diffDays < 7) return `${diffDays}天前`;
    return date.toLocaleDateString();
  }

  function formatCount(count: number): string {
    if (count >= 10000) {
      return (count / 10000).toFixed(1) + '万';
    }
    return count.toString();
  }

  if (!isLoggedIn) {
    return (
      <div className="min-h-screen bg-gray-50 dark:bg-gray-900 py-6">
        <div className="max-w-7xl mx-auto px-4">
          <div className="text-center py-20 text-gray-500">
            <Users className="w-16 h-16 mx-auto mb-4 opacity-50" />
            <p className="text-lg font-medium">请先登录</p>
            <p className="text-sm mt-2">登录后可以查看关注创作者的动态</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900 py-6">
      <div className="max-w-7xl mx-auto px-4">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-6"
        >
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <Users className="w-6 h-6" />
            动态
          </h1>
          <p className="text-gray-500 mt-1">关注创作者的最新作品</p>
        </motion.div>

        {/* 竖向列表 - 横向充满 */}
        {videos.length > 0 && (
          <div className="space-y-6">
            {videos.map((video, index) => (
              <motion.div
                key={video.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: Math.min(index * 0.05, 0.3) }}
                onClick={() => navigate(`/video/${video.id}`)}
                className="bg-white dark:bg-gray-800 rounded-xl shadow-sm hover:shadow-md transition-shadow cursor-pointer overflow-hidden w-full"
              >
                <div className="flex flex-col md:flex-row">
                  {/* 左侧封面 - 固定宽度 */}
                  <div className="md:w-80 flex-shrink-0">
                    <div className="aspect-video md:aspect-video relative overflow-hidden bg-gray-200">
                      <img
                        src={video.coverUrl}
                        alt={video.title}
                        className="w-full h-full object-cover"
                        onError={(e) => {
                          e.currentTarget.src = 'https://images.unsplash.com/photo-1611162616475-46b635cb6868?w=640&h=360&fit=crop';
                        }}
                      />
                      <div className="absolute bottom-2 right-2 px-2 py-1 bg-black/70 text-white text-xs rounded">
                        {Math.floor(video.duration / 60)}:{(video.duration % 60).toString().padStart(2, '0')}
                      </div>
                    </div>
                  </div>

                  {/* 右侧内容 - 自适应宽度 */}
                  <div className="flex-1 p-5 min-w-0">
                    {/* 作者信息 */}
                    <div className="flex items-center gap-3 mb-3">
                      <img
                        src={video.uploaderAvatar}
                        alt={video.uploaderName}
                        className="w-10 h-10 rounded-full object-cover flex-shrink-0"
                      />
                      <div className="min-w-0">
                        <Link 
                          to={`/user/${video.uploaderId}`}
                          onClick={(e) => e.stopPropagation()}
                          className="font-semibold text-gray-900 dark:text-white hover:text-blue-500"
                        >
                          {video.uploaderName}
                        </Link>
                        <div className="flex items-center gap-1 text-xs text-gray-500">
                          <Calendar className="w-3 h-3" />
                          <span>{formatDate(video.uploadTime)}</span>
                        </div>
                      </div>
                    </div>

                    {/* 标题 */}
                    <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-2 line-clamp-1">
                      {video.title}
                    </h3>

                    {/* 简介 */}
                    <p className="text-gray-600 dark:text-gray-400 text-sm mb-3 line-clamp-2">
                      {video.description || '暂无简介'}
                    </p>

                    {/* 统计数据 */}
                    <div className="flex items-center gap-5 text-sm text-gray-500">
                      <span className="flex items-center gap-1">
                        <Eye className="w-4 h-4" />
                        {formatCount(video.viewCount)}
                      </span>
                      <span className="flex items-center gap-1">
                        <Heart className="w-4 h-4" />
                        {formatCount(video.likeCount)}
                      </span>
                      <span className="flex items-center gap-1">
                        <MessageCircle className="w-4 h-4" />
                        {formatCount(video.commentCount)}
                      </span>
                    </div>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        )}

        {!isLoading && videos.length === 0 && (
          <div className="text-center py-20 text-gray-500">
            <Users className="w-16 h-16 mx-auto mb-4 opacity-50" />
            <p className="text-lg font-medium">暂无动态</p>
            <p className="text-sm mt-2">
              关注创作者后，他们的新作品会出现在这里
            </p>
          </div>
        )}

        {isLoading && (
          <div className="flex justify-center py-8">
            <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
          </div>
        )}

        {!hasMore && videos.length > 0 && (
          <p className="text-center text-gray-500 py-8">没有更多内容了</p>
        )}
      </div>
    </div>
  );
}

export default SubscriptionPage;