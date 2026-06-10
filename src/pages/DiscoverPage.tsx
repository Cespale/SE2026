import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { Loader2, Radio, Users } from 'lucide-react';
import { useLiveStore } from '../stores/liveStore';

export const DiscoverPage: React.FC = () => {
  const navigate = useNavigate();
  const [refreshing, setRefreshing] = useState(false);

  const {
    rooms,
    isLoading,
    fetchRooms,
  } = useLiveStore();

  const handleRefresh = async () => {
    setRefreshing(true);
    await fetchRooms();
    setRefreshing(false);
  };

  useEffect(() => {
    fetchRooms();
  }, [fetchRooms]);

  // 只显示正在直播的房间 (status === 1)
  const liveRooms = rooms.filter((room) => room.status === 1);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            正在直播
          </h1>
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="flex items-center gap-2 px-3 py-1.5 text-sm bg-white dark:bg-gray-800 border rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
          >
            <Loader2 className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            刷新
          </button>
        </div>

        {isLoading && (
          <div className="flex justify-center py-8">
            <Loader2 className="w-8 h-8 animate-spin text-red-500" />
          </div>
        )}

        {!isLoading && liveRooms.length === 0 && (
          <div className="flex flex-col items-center justify-center py-24 text-gray-500">
            <Radio className="w-16 h-16 mb-4 opacity-60" />
            <p className="text-lg font-medium">暂无正在直播的房间</p>
            <p className="text-sm mt-2">创作者可以点击“开始直播”创建直播间。</p>
          </div>
        )}

        {!isLoading && liveRooms.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {liveRooms.map((room, index) => (
              <motion.div
                key={room.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: Math.min(index * 0.04, 0.3) }}
                onClick={() => navigate(`/live/${room.id}`)}
                className="bg-white dark:bg-gray-800 rounded-xl overflow-hidden shadow-sm cursor-pointer hover:shadow-md transition-shadow"
              >
                <div className="relative aspect-video bg-gray-200 dark:bg-gray-700">
                  <img
                    src={room.cover}
                    alt={room.title}
                    className="w-full h-full object-cover"
                    onError={(e) => {
                      e.currentTarget.src = 'https://images.unsplash.com/photo-1611162616475-46b635cb6868?w=900&auto=format&fit=crop';
                    }}
                  />

                  <div className="absolute top-3 left-3 px-3 py-1 bg-red-500 text-white text-xs font-bold rounded-full animate-pulse">
                    LIVE
                  </div>

                  <div className="absolute bottom-3 right-3 px-2 py-1 bg-black/70 text-white text-xs rounded-full flex items-center gap-1">
                    <Users className="w-3 h-3" />
                    {room.onlineCount}
                  </div>
                </div>

                <div className="p-4">
                  <h3 className="font-bold text-gray-900 dark:text-white line-clamp-1">
                    {room.title}
                  </h3>

                  <div className="flex items-center gap-3 mt-3">
                    <img
                      src={room.anchorAvatar}
                      alt={room.anchorName}
                      className="w-9 h-9 rounded-full bg-gray-200"
                      onError={(e) => {
                        e.currentTarget.src =
                          'https://api.dicebear.com/7.x/avataaars/svg?seed=creator';
                      }}
                    />

                    <div className="min-w-0">
                      <p className="text-sm text-gray-700 dark:text-gray-300 truncate">
                        {room.anchorName}
                      </p>
                      <p className="text-xs text-gray-500">
                        {room.categoryName}
                      </p>
                    </div>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default DiscoverPage;