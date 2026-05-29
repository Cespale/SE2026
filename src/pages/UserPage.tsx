import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { motion } from 'framer-motion';
import { VideoCard } from '../components/video/VideoCard';
import { useVideoStore } from '../stores/videoStore';
import { useAuthStore } from '../stores/authStore';
import { User, Heart, Video, Users } from 'lucide-react';
import { FollowButton } from '../components/social/FollowButton';
import { getUserProfile, getRelation, Relation } from '../api/social';
import { MessageCircle } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const mockUserVideos = [
  {
    id: '1',
    title: '我的第一个视频',
    description: '这是我的第一个视频作品',
    tags: ['生活', 'Vlog'],
    coverUrl: 'https://images.unsplash.com/photo-1492691527719-9d1e07e534b4?w=640&h=360&fit=crop',
    videoUrl: '',
    duration: 180,
    categoryId: '5',
    categoryName: '生活',
    viewCount: 1200,
    likeCount: 89,
    commentCount: 12,
    favoriteCount: 45,
    uploaderId: '2',
    uploaderName: '创作者小王',
    uploaderAvatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=creator',
    uploadTime: '2024-01-10T10:00:00Z',
    auditStatus: 1
  },
  {
    id: '2',
    title: '游戏精彩集锦',
    description: '王者荣耀精彩操作',
    tags: ['游戏', '王者荣耀'],
    coverUrl: 'https://images.unsplash.com/photo-1542751371-adc38448a05e?w=640&h=360&fit=crop',
    videoUrl: '',
    duration: 240,
    categoryId: '1',
    categoryName: '游戏',
    viewCount: 5600,
    likeCount: 456,
    commentCount: 78,
    favoriteCount: 234,
    uploaderId: '2',
    uploaderName: '创作者小王',
    uploaderAvatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=creator',
    uploadTime: '2024-01-08T15:00:00Z',
    auditStatus: 1
  }
];

const mockLikedVideos = [
  {
    id: '3',
    title: '科技前沿解读',
    description: '最新科技动态',
    tags: ['科技'],
    coverUrl: 'https://images.unsplash.com/photo-1677442136019-21780ecad995?w=640&h=360&fit=crop',
    videoUrl: '',
    duration: 300,
    categoryId: '4',
    categoryName: '科技',
    viewCount: 8900,
    likeCount: 678,
    commentCount: 123,
    favoriteCount: 345,
    uploaderId: '3',
    uploaderName: '普通用户',
    uploaderAvatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=user',
    uploadTime: '2024-01-05T09:00:00Z',
    auditStatus: 1
  }
];

export function UserPage() {
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

  const videos = activeTab === 'works' ? mockUserVideos : mockLikedVideos;

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
                  <span className="font-semibold">{userInfo.followers}</span>
                  <span className="text-gray-500">粉丝</span>
                </div>
                <div className="flex items-center gap-2">
                  <User className="w-4 h-4 text-gray-500" />
                  <span className="font-semibold">{userInfo.following}</span>
                  <span className="text-gray-500">关注</span>
                </div>
                <div className="flex items-center gap-2">
                  <Heart className="w-4 h-4 text-gray-500" />
                  <span className="font-semibold">{userInfo.likes}</span>
                  <span className="text-gray-500">获赞</span>
                </div>
              </div>
            </div>
            <div className="flex gap-3">
              {isOwnProfile ? (
                <button className="px-6 py-2 bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white rounded-full hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors">
                  编辑资料
                </button>
              ) : (
                id && (
                  <>
                    <FollowButton
                      userId={id}
                      onChange={(isFollowing) => {
                        setRelation((r) =>
                          r
                            ? {
                                ...r,
                                isFollowing,
                                isMutual: isFollowing && r.isFollowedBy,
                                followerCount: r.followerCount + (isFollowing ? 1 : -1),
                              }
                            : r
                        );
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
          {videos.map((video, index) => (
            <motion.div
              key={video.id}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.05 }}
            >
              <VideoCard video={video} />
            </motion.div>
          ))}
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
