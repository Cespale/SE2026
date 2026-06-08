import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Video, Heart, History, Settings, User } from 'lucide-react';
import { VideoCard } from '../components/video/VideoCard';
import { useAuthStore } from '../stores/authStore';
import { useNavigate } from 'react-router-dom';
import { apiRequest } from '../api';

export function ProfilePage() {
  const [activeTab, setActiveTab] = useState<'works' | 'likes' | 'history'>('works');
  const { user } = useAuthStore();
  const navigate = useNavigate();

  const [works, setWorks] = useState<any[]>([]);
  const [likes, setLikes] = useState<any[]>([]);
  const [history, setHistory] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const tabs = [
    { id: 'works' as const, label: '我的作品', icon: Video },
    { id: 'likes' as const, label: '我的喜欢', icon: Heart },
    { id: 'history' as const, label: '观看历史', icon: History },
  ];

  // 获取我的作品
  const fetchWorks = async () => {
    try {
      const data = await apiRequest('/api/creator/videos');
      setWorks(data.items || []);
    } catch (error) {
      console.error('获取作品失败:', error);
      setWorks([]);
    }
  };

  // 获取喜欢的视频
  const fetchLikes = async () => {
    // 后端可能需要实现收藏接口，暂时返回空数组
    setLikes([]);
  };

  // 获取观看历史
  const fetchHistory = async () => {
    // 后端可能需要实现历史记录接口，暂时返回空数组
    setHistory([]);
  };

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await fetchWorks();
      await fetchLikes();
      await fetchHistory();
      setLoading(false);
    };
    loadData();
  }, []);

  /* 
  const getVideos = () => {
    switch (activeTab) {
      case 'works': return mockVideos;
      case 'likes': return mockVideos;
      case 'history': return mockHistory;
      default: return [];
    }
  };
  */

  const getVideos = () => {
    switch (activeTab) {
      case 'works': return works;
      case 'likes': return likes;
      case 'history': return history;
      default: return [];
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="fixed top-20 right-4 z-50 bg-red-500 text-white px-3 py-1 rounded-full text-sm font-bold shadow-lg">
        🚀 新版本 - 下午修改
      </div>
      <div className="max-w-7xl mx-auto px-4 py-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white dark:bg-gray-800 rounded-2xl p-8 mb-8"
        >
          <div className="flex items-start gap-6">
            <img
              src={user?.avatar}
              alt={user?.nickname}
              className="w-24 h-24 rounded-full object-cover border-4 border-white dark:border-gray-700 shadow-lg"
            />
            <div className="flex-1">
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
                {user?.nickname}
              </h1>
              <p className="text-gray-600 dark:text-gray-400 mb-4">{user?.bio || '暂无简介'}</p>
              <div className="flex items-center gap-6 text-sm text-gray-500">
                <span>粉丝 1,234</span>
                <span>关注 56</span>
                <span>获赞 5,678</span>
              </div>
            </div>
            <button
              onClick={() => navigate('/settings')}
              className="flex items-center gap-2 px-4 py-2 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
            >
              <Settings className="w-4 h-4" />
              设置
            </button>
          </div>
        </motion.div>

        <div className="flex items-center gap-6 border-b border-gray-200 dark:border-gray-800 mb-6">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 pb-4 text-lg font-medium transition-colors ${
                activeTab === tab.id
                  ? 'text-blue-500 border-b-2 border-blue-500'
                  : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
              }`}
            >
              <tab.icon className="w-5 h-5" />
              {tab.label}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
          {loading ? (
            <div className="col-span-full text-center py-20 text-gray-500">加载中...</div>
          ) : (
            getVideos().map((video, index) => (
              <motion.div
                key={video.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.05 }}
              >
                <VideoCard video={video} />
              </motion.div>
            ))
          )}
        </div>

        {getVideos().length === 0 && (
          <div className="text-center py-20 text-gray-500">
            <User className="w-16 h-16 mx-auto mb-4 opacity-50" />
            <p>暂无内容</p>
          </div>
        )}
      </div>
    </div>
  );
}
