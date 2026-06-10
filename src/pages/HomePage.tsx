import React, { useEffect, useCallback, useState } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { useVideoStore } from '../stores/videoStore';
import { VideoCard } from '../components/video/VideoCard';
import { CategoryBar } from '../components/video/CategoryBar';
import { Loader2, Video } from 'lucide-react';
import { useAuthStore } from '../stores/authStore';

export function HomePage() {
  const navigate = useNavigate();
  const { isLoggedIn } = useAuthStore();

  const {
    videos,
    categories,
    isLoading,
    hasMore,
    fetchVideos,
    fetchCategories,
    fetchRecommendedVideos,
    loadMore,
  } = useVideoStore();

  const [selectedCategory, setSelectedCategory] = useState('recommended');

  useEffect(() => {
    fetchCategories();
    if (isLoggedIn) {
      fetchRecommendedVideos(1);
    } else {
      fetchVideos({ page: 1 });
    }
  }, [fetchCategories, fetchVideos, fetchRecommendedVideos, isLoggedIn]);

  useEffect(() => {
    if (selectedCategory === 'recommended') {
      if (isLoggedIn) {
        fetchRecommendedVideos(1);
      } else {
        fetchVideos({ page: 1 });
      }
    } else if (selectedCategory) {
      fetchVideos({ categoryId: selectedCategory, page: 1 });
    }
  }, [selectedCategory, fetchVideos, fetchRecommendedVideos, isLoggedIn]);

  const handleCategoryChange = (categoryId: string) => {
    setSelectedCategory(categoryId);
  };

  const handleScroll = useCallback(() => {
    const nearBottom =
      window.innerHeight + window.scrollY >= document.body.offsetHeight - 120;

    if (nearBottom && hasMore && !isLoading) {
      if (selectedCategory === 'recommended') {
        const nextPage = Math.floor(videos.length / 20) + 1;
        fetchRecommendedVideos(nextPage);
      } else {
        loadMore(selectedCategory);
      }
    }
  }, [hasMore, isLoading, loadMore, selectedCategory, fetchRecommendedVideos, videos.length]);

  useEffect(() => {
    window.addEventListener('scroll', handleScroll);

    return () => {
      window.removeEventListener('scroll', handleScroll);
    };
  }, [handleScroll]);

  const realCategories = categories.filter(
    (category) => category.type === 0 && category.name !== '推荐'
  );
  
  const visibleCategories = [
    { id: 'recommended', name: '推荐', type: 0 },
    ...realCategories,
  ];

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <CategoryBar
        categories={visibleCategories}
        activeId={selectedCategory}
        onSelect={handleCategoryChange}
      />

      <div className="px-4 py-6">
        {videos.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
            {videos.map((video, index) => (
              <motion.div
                key={video.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: Math.min(index * 0.03, 0.3) }}
              >
                <VideoCard
                  video={video}
                  onClick={() => navigate(`/video/${video.id}`)}
                />
              </motion.div>
            ))}
          </div>
        )}

        {!isLoading && videos.length === 0 && (
          <div className="flex flex-col items-center justify-center py-24 text-gray-500">
            <Video className="w-16 h-16 mb-4 opacity-60" />
            <p className="text-lg font-medium">暂无视频内容</p>
            <p className="text-sm mt-2">
              可以切换分类，或者使用创作者账号上传视频后再查看。
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

export default HomePage;