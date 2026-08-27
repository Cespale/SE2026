import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { VideoCard } from '../components/video/VideoCard';
import { useVideoStore } from '../stores/videoStore';
import { useAuthStore } from '../stores/authStore';
import { User, Heart, Video, Users } from 'lucide-react';
import { FollowButton } from '../components/social/FollowButton';
import { getUserProfile, getRelation, Relation } from '../api/social';
import { API_BASE } from '../api';
import { MessageCircle } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export function UserPage() {
  const [works, setWorks] = useState<any[]>([]);
  const [likes, setLikes] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState<'works' | 'likes'>('works');
  const { user: currentUser, isLoggedIn, openLoginModal } = useAuthStore();
  const isOwnProfile = currentUser?.id === id;

  const [profile, setProfile] = useState<any>(null);
  const [relation, setRelation] = useState<Relation | null>(null);

  useEffect(() => {
    if (!id) return;
    getUserProfile(id).then(setProfile).catch(() => setProfile(null));
    if (!isOwnProfile) {
      getRelation(id).then(setRelation).catch(() => setRelation(null));
    } else {
      // 看自己主页时也想知道粉丝/关注数,借用 relation 接口(对自己 isFollowing 永远 false)
      getRelation(id).then(setRelation).catch(() => setRelation(null));
    }
  }, [id, isOwnProfile]);

  const userInfo = {
    id: id || '',
    nickname: profile?.nickname || '加载中...',
    avatar: profile?.avatar || 'https://api.dicebear.com/7.x/avataaars/svg?seed=user',
    bio: profile?.bio || '',
    followers: relation?.followerCount ?? 0,
    following: relation?.followingCount ?? 0,
    likes: 0,
  };

  // 获取用户的视频作品
  const fetchUserVideos = async () => {
    if (!id) return;
    try {
      // 调用获取用户视频的接口（需要后端支持）
      const response = await fetch(`${API_BASE}/api/users/${id}/videos`);
      const data = await response.json();
      setWorks(data.items || []);
    } catch (error) {
      console.error('获取用户视频失败:', error);
      setWorks([]);
    }
  };

  // 获取用户喜欢的视频
  const fetchUserLikes = async () => {
    if (!id) return;
    try {
      const response = await fetch(`${API_BASE}/api/users/${id}/likes`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('auth-storage') ? JSON.parse(localStorage.getItem('auth-storage')!).state?.token : ''}`
        }
      });
      const data = await response.json();
      setLikes(data.items || []);
    } catch (error) {
      console.error('获取用户喜欢失败:', error);
      setLikes([]);
    }
  };

  const [stats, setStats] = useState({ followerCount: 0, followingCount: 0, likeCount: 0 });

  const fetchUserStats = async () => {
    if (!id) return;
    try {
      const response = await fetch(`${API_BASE}/api/users/${id}/stats`);
      const data = await response.json();
      setStats({
        followerCount: data.followerCount || 0,
        followingCount: data.followingCount || 0,
        likeCount: data.likeCount || 0
      });
    } catch (error) {
      console.error('获取用户统计失败:', error);
    }
  };

  // 组件加载时获取数据
  useEffect(() => {
    if (!id) return;
    getUserProfile(id).then(setProfile).catch(() => setProfile(null));
    fetchUserStats();
    if (!isOwnProfile) {
      getRelation(id).then(setRelation).catch(() => setRelation(null));
    } else {
      getRelation(id).then(setRelation).catch(() => setRelation(null));
    }
    
    // 加载视频数据
    const loadVideos = async () => {
      setLoading(true);
      await fetchUserVideos();
      await fetchUserLikes();
      setLoading(false);
    };
    loadVideos();
  }, [id, isOwnProfile]);

  // const videos = activeTab === 'works' ? mockUserVideos : mockLikedVideos;
  const videos = activeTab === 'works' ? works : likes;

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="max-w-7xl mx-auto px-4 py-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white dark:bg-gray-800 rounded-2xl p-8 mb-8"
        >
          <div className="flex items-start gap-6">
            <img
              src={userInfo.avatar}
              alt={userInfo.nickname}
              className="w-24 h-24 rounded-full object-cover border-4 border-white dark:border-gray-700 shadow-lg"
            />
            <div className="flex-1">
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
                {userInfo.nickname}
              </h1>
              <p className="text-gray-600 dark:text-gray-400 mb-4">{userInfo.bio}</p>
              <div className="flex items-center gap-6 text-sm">
                <div className="flex items-center gap-2">
                  <Users className="w-4 h-4 text-gray-500" />
                  <span className="font-semibold">{stats.followerCount}</span>
                  <span className="text-gray-500">粉丝</span>
                </div>
                <div className="flex items-center gap-2">
                  <User className="w-4 h-4 text-gray-500" />
                  <span className="font-semibold">{stats.followingCount}</span>
                  <span className="text-gray-500">关注</span>
                </div>
                <div className="flex items-center gap-2">
                  <Heart className="w-4 h-4 text-gray-500" />
                  <span className="font-semibold">{stats.likeCount}</span>
                  <span className="text-gray-500">获赞</span>
                </div>
              </div>
            </div>
            <div className="flex gap-3">
              {isOwnProfile ? (
                <button 
                  onClick={() => navigate('/settings')}
                  className="px-6 py-2 bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white rounded-full hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
                >
                  编辑资料
                </button>
              ) : (
                id && (
                  <>
                    <FollowButton
                      userId={id}
                      onChange={(isFollowing) => {
                        setRelation((r) => r ? { ...r, isFollowing } : r);
                        // 更新统计数据
                        setStats(prev => ({
                          ...prev,
                          followerCount: prev.followerCount + (isFollowing ? 1 : -1)
                        }));
                      }}
                    />
                    <button
                      onClick={() => {
                        if (!isLoggedIn) {
                          openLoginModal();
                          return;
                        }
                        navigate(`/messages?peer=${id}`);
                      }}
                      className="px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white rounded-full hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors flex items-center gap-1.5"
                    >
                      <MessageCircle className="w-4 h-4" />
                      发消息
                    </button>
                  </>
                )
              )}
            </div>
          </div>
        </motion.div>

        <div className="flex items-center gap-6 border-b border-gray-200 dark:border-gray-800 mb-6">
          <button
            onClick={() => setActiveTab('works')}
            className={`flex items-center gap-2 pb-4 text-lg font-medium transition-colors ${
              activeTab === 'works'
                ? 'text-blue-500 border-b-2 border-blue-500'
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
            }`}
          >
            <Video className="w-5 h-5" />
            作品
          </button>
          <button
            onClick={() => setActiveTab('likes')}
            className={`flex items-center gap-2 pb-4 text-lg font-medium transition-colors ${
              activeTab === 'likes'
                ? 'text-blue-500 border-b-2 border-blue-500'
                : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'
            }`}
          >
            <Heart className="w-5 h-5" />
            喜欢
          </button>
        </div>

                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
          {loading ? (
            <div className="col-span-full text-center py-20 text-gray-500">加载中...</div>
          ) : (
            videos.map((video, index) => (
              <motion.div
                key={video.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.05 }}
              >
                <VideoCard 
                  video={video} 
                  onClick={() => navigate(`/video/${video.id}`)}
                />
              </motion.div>
            ))
          )}
        </div>

        {videos.length === 0 && (
          <div className="text-center py-20 text-gray-500">
            <Video className="w-16 h-16 mx-auto mb-4 opacity-50" />
            <p>暂无{activeTab === 'works' ? '作品' : '喜欢'}内容</p>
          </div>
        )}
      </div>
    </div>
  );
}
