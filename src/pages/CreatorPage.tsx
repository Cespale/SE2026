import React, { useEffect, useMemo, useState } from 'react';
import {
  LayoutDashboard,
  Video,
  Users,
  MessageSquare,
  Eye,
  Heart,
  Bookmark,
  Loader2,
  Upload,
  PlayCircle,
} from 'lucide-react';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import { useVideoStore, Video as VideoItem } from '../stores/videoStore';
import { getCreatorFans, getCreatorComments } from '../api';
import { apiRequest } from '../api';

const DEFAULT_AVATAR =
  'https://api.dicebear.com/7.x/avataaars/svg?seed=creator';

const DEFAULT_COVER_URL =
  'https://images.unsplash.com/photo-1611162616475-46b635cb6868?w=900&auto=format&fit=crop';

const menuItems = [
  { id: 'overview', label: '数据概览', icon: LayoutDashboard },
  { id: 'content', label: '内容管理', icon: Video },
  { id: 'fans', label: '粉丝管理', icon: Users },
  { id: 'comments', label: '评论管理', icon: MessageSquare },
];

function formatCount(count?: number) {
  const safeCount = Number(count || 0);
  if (safeCount >= 10000) {
    return (safeCount / 10000).toFixed(1) + '万';
  }
  return safeCount.toString();
}

function getAuditLabel(status: number) {
  if (status === 1) return '已通过';
  if (status === 2) return '已驳回';
  return '审核中';
}

function getAuditClass(status: number) {
  if (status === 1) return 'bg-green-100 text-green-600';
  if (status === 2) return 'bg-red-100 text-red-600';
  return 'bg-yellow-100 text-yellow-600';
}

function formatDuration(seconds?: number) {
  const safeSeconds = Number(seconds || 0);
  if (!Number.isFinite(safeSeconds) || safeSeconds <= 0) {
    return '0:00';
  }
  const mins = Math.floor(safeSeconds / 60);
  const secs = Math.floor(safeSeconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export function CreatorPage() {
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState('overview');
  const [creatorVideos, setCreatorVideos] = useState<VideoItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState('');

  const [fans, setFans] = useState<any[]>([]);
  const [comments, setComments] = useState<any[]>([]);
  const [fansCount, setFansCount] = useState(0);
  const [isLoadingFans, setIsLoadingFans] = useState(false);
  const [isLoadingComments, setIsLoadingComments] = useState(false);

  const [filterStatus, setFilterStatus] = useState<number | 'all'>('all');
  const [filteredVideos, setFilteredVideos] = useState<VideoItem[]>([]);
  const [isDeleting, setIsDeleting] = useState<string | null>(null);
  const [isDeletingComment, setIsDeletingComment] = useState<string | null>(null);

  // 编辑视频相关状态
  const [editingVideo, setEditingVideo] = useState<VideoItem | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editCategoryId, setEditCategoryId] = useState('');
  const [isSubmittingEdit, setIsSubmittingEdit] = useState(false);
  const { categories, fetchCategories } = useVideoStore();

  const { user } = useAuthStore();
  const { fetchCreatorVideos } = useVideoStore();

  const loadCreatorVideos = async () => {
    setIsLoading(true);
    setMessage('');
    try {
      const list = await fetchCreatorVideos();
      setCreatorVideos(list);
    } catch (error) {
      console.error('获取创作者视频失败:', error);
      setCreatorVideos([]);
      setMessage('获取创作者视频失败，请检查后端是否启动或是否已登录创作者账号。');
    } finally {
      setIsLoading(false);
    }
  };

  const loadFans = async () => {
    setIsLoadingFans(true);
    try {
      const data = await getCreatorFans();
      setFans(data.items || []);
      setFansCount(data.total || 0);
    } catch (error) {
      console.error('获取粉丝列表失败:', error);
    } finally {
      setIsLoadingFans(false);
    }
  };

  const loadComments = async () => {
    setIsLoadingComments(true);
    try {
      const data = await getCreatorComments();
      setComments(data.items || []);
    } catch (error) {
      console.error('获取评论列表失败:', error);
    } finally {
      setIsLoadingComments(false);
    }
  };

  const loadVideosByStatus = async (status: number | 'all') => {
    setIsLoading(true);
    try {
      let list: VideoItem[];
      if (status === 'all') {
        const data = await apiRequest('/api/creator/videos');
        list = data.items || [];
      } else {
        const data = await apiRequest(`/api/creator/videos/${status}`);
        list = data.items || [];
      }
      setFilteredVideos(list);
    } catch (error) {
      console.error('获取视频列表失败:', error);
      setFilteredVideos([]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteVideo = async (videoId: string) => {
    if (!confirm('确定要删除这个视频吗？此操作不可恢复。')) return;
    setIsDeleting(videoId);
    try {
      await apiRequest(`/api/creator/videos/${videoId}`, { method: 'DELETE' });
      await loadVideosByStatus(filterStatus);
      await loadCreatorVideos();
    } catch (error) {
      console.error('删除失败:', error);
      alert('删除失败，请稍后重试');
    } finally {
      setIsDeleting(null);
    }
  };

  const handleDeleteComment = async (commentId: string) => {
    if (!confirm('确定要删除这条评论吗？此操作不可恢复。')) return;
    setIsDeletingComment(commentId);
    try {
      await apiRequest(`/api/creator/comments/${commentId}`, { method: 'DELETE' });
      await loadComments();
    } catch (error) {
      console.error('删除评论失败:', error);
      alert('删除失败，请稍后重试');
    } finally {
      setIsDeletingComment(null);
    }
  };

  const handleEditVideo = async () => {
    if (!editingVideo) return;
    if (!editTitle.trim()) {
      alert('请填写标题');
      return;
    }
    setIsSubmittingEdit(true);
    try {
      await apiRequest(`/api/creator/videos/${editingVideo.id}`, {
        method: 'PUT',
        body: JSON.stringify({
          title: editTitle.trim(),
          description: editDescription.trim() || '',
          category_id: editCategoryId ? parseInt(editCategoryId) : null,
        }),
      });
      await loadCreatorVideos();
      await loadVideosByStatus(filterStatus);
      setEditingVideo(null);
    } catch (error) {
      console.error('编辑失败:', error);
      alert('编辑失败，请稍后重试');
    } finally {
      setIsSubmittingEdit(false);
    }
  };

  const openEditDialog = (video: VideoItem) => {
    setEditingVideo(video);
    setEditTitle(video.title);
    setEditDescription(video.description || '');
    const matchedCategory = categories.find(c => c.id === video.categoryId);
    setEditCategoryId(matchedCategory ? matchedCategory.id : video.categoryId);
  };

  const navigateToContentWithFilter = (status: number | 'all') => {
    setActiveTab('content');
    setFilterStatus(status);
    loadVideosByStatus(status);
  };

  useEffect(() => {
    fetchCategories();
    const init = async () => {
      await loadCreatorVideos();
      await loadFans();
      await loadComments();
      await loadVideosByStatus('all');
    };
    init();
  }, []);

  const stats = useMemo(() => {
    const totalViews = creatorVideos.reduce((sum, video) => sum + Number(video.viewCount || 0), 0);
    const totalLikes = creatorVideos.reduce((sum, video) => sum + Number(video.likeCount || 0), 0);
    const totalFavorites = creatorVideos.reduce((sum, video) => sum + Number(video.favoriteCount || 0), 0);
    const approvedCount = creatorVideos.filter((video) => video.auditStatus === 1).length;
    const pendingCount = creatorVideos.filter((video) => video.auditStatus === 0).length;
    const rejectedCount = creatorVideos.filter((video) => video.auditStatus === 2).length;
    return { totalViews, totalLikes, totalFavorites, totalFans: fansCount, approvedCount, pendingCount, rejectedCount };
  }, [creatorVideos, fansCount]);

  const renderOverview = () => (
    <div className="space-y-6">
      {message && <div className="p-3 rounded-lg bg-blue-50 text-blue-700 text-sm">{message}</div>}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-sm">
          <div className="flex items-center gap-3 mb-2"><Eye className="w-5 h-5 text-blue-500" /><span className="text-gray-500">总播放量</span></div>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">{formatCount(stats.totalViews)}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-sm">
          <div className="flex items-center gap-3 mb-2"><Users className="w-5 h-5 text-green-500" /><span className="text-gray-500">粉丝数</span></div>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">{formatCount(stats.totalFans)}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-sm">
          <div className="flex items-center gap-3 mb-2"><Heart className="w-5 h-5 text-red-500" /><span className="text-gray-500">获赞数</span></div>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">{formatCount(stats.totalLikes)}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-sm">
          <div className="flex items-center gap-3 mb-2"><Bookmark className="w-5 h-5 text-yellow-500" /><span className="text-gray-500">收藏数</span></div>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">{formatCount(stats.totalFavorites)}</p>
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-green-50 dark:bg-green-900/20 p-5 rounded-xl cursor-pointer hover:bg-green-100 transition-colors" onClick={() => navigateToContentWithFilter(1)}>
          <p className="text-sm text-green-600">已通过视频</p><p className="text-2xl font-bold text-green-700">{stats.approvedCount}</p>
        </div>
        <div className="bg-yellow-50 dark:bg-yellow-900/20 p-5 rounded-xl cursor-pointer hover:bg-yellow-100 transition-colors" onClick={() => navigateToContentWithFilter(0)}>
          <p className="text-sm text-yellow-600">审核中视频</p><p className="text-2xl font-bold text-yellow-700">{stats.pendingCount}</p>
        </div>
        <div className="bg-red-50 dark:bg-red-900/20 p-5 rounded-xl cursor-pointer hover:bg-red-100 transition-colors" onClick={() => navigateToContentWithFilter(2)}>
          <p className="text-sm text-red-600">未通过视频</p><p className="text-2xl font-bold text-red-700">{stats.rejectedCount}</p>
        </div>
      </div>
    </div>
  );

  const renderContent = () => {
    const statusTabs = [
      { label: '全部', value: 'all', count: creatorVideos.length },
      { label: '已通过', value: 1, count: creatorVideos.filter(v => v.auditStatus === 1).length },
      { label: '审核中', value: 0, count: creatorVideos.filter(v => v.auditStatus === 0).length },
      { label: '未通过', value: 2, count: creatorVideos.filter(v => v.auditStatus === 2).length },
    ];
    const displayVideos = filteredVideos;
    return (
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm overflow-hidden">
        <div className="flex items-center justify-between p-4 border-b border-gray-100 dark:border-gray-700">
          <div><h3 className="font-bold text-gray-900 dark:text-white">内容管理</h3><p className="text-sm text-gray-500">查看自己上传的视频及审核状态。</p></div>
          <div className="flex gap-2">
            <button onClick={() => { loadCreatorVideos(); loadVideosByStatus(filterStatus); }} className="px-3 py-2 text-sm border rounded-lg hover:bg-gray-50">刷新</button>
            <button onClick={() => navigate('/upload')} className="px-3 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center gap-2"><Upload className="w-4 h-4" />上传视频</button>
          </div>
        </div>
        {/* 状态筛选标签 - 均匀分布 */}
        <div className="flex gap-2 px-4 pt-3 border-b border-gray-100 dark:border-gray-700">
          {statusTabs.map((tab) => (
            <button
              key={tab.value}
              onClick={() => { 
                setFilterStatus(tab.value as number | 'all'); 
                loadVideosByStatus(tab.value as number | 'all'); 
              }}
              className={`flex-1 px-4 py-2 text-sm rounded-t-lg transition-colors text-center ${
                filterStatus === tab.value
                  ? 'bg-blue-500 text-white'
                  : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
              }`}
            >
              {tab.label} ({tab.count})
            </button>
          ))}
        </div>
        {isLoading ? <div className="px-4 py-12 text-center"><Loader2 className="w-8 h-8 animate-spin mx-auto mb-3 text-blue-500" />正在加载...</div>
        : displayVideos.length === 0 ? <div className="px-4 py-12 text-center text-gray-500"><Video className="w-12 h-12 mx-auto mb-3 opacity-60" />暂无投稿视频</div>
        : <div className="overflow-x-auto"><table className="w-full min-w-[900px]"><thead className="bg-gray-50"><tr><th className="px-4 py-3 text-left w-[35%]">视频</th><th className="px-4 py-3 text-left w-[10%]">播放量</th><th className="px-4 py-3 text-left w-[8%]">点赞</th><th className="px-4 py-3 text-left w-[8%]">收藏</th><th className="px-4 py-3 text-left w-[10%]">状态</th><th className="px-4 py-3 text-left w-[12%]">时间</th><th className="px-4 py-3 text-left w-[17%]">操作</th></tr></thead>
        <tbody>{displayVideos.map((video) => (<tr key={video.id} className="border-t"><td className="px-4 py-3"><div className="flex items-center gap-3"><img src={video.coverUrl || DEFAULT_COVER_URL} alt={video.title} className="w-20 h-12 object-cover rounded" /><div><p className="font-medium line-clamp-1 text-sm">{video.title}</p><p className="text-xs text-gray-500">{formatDuration(video.duration)}</p></div></div></td>
        <td className="px-4 py-3 text-sm">{formatCount(video.viewCount)}</td><td className="px-4 py-3 text-sm">{formatCount(video.likeCount)}</td><td className="px-4 py-3 text-sm">{formatCount(video.favoriteCount)}</td>
        <td className="px-4 py-3"><span className={`px-2 py-1 rounded-full text-xs whitespace-nowrap ${getAuditClass(video.auditStatus)}`}>{getAuditLabel(video.auditStatus)}</span></td>
        <td className="px-4 py-3 text-sm whitespace-nowrap">{new Date(video.uploadTime).toLocaleDateString()}</td>
        <td className="px-4 py-3"><div className="flex gap-2"><button onClick={() => navigate(`/video/${video.id}`)} className="px-3 py-1.5 text-sm bg-gray-100 rounded-lg hover:bg-blue-50">预览</button>
        <button onClick={() => openEditDialog(video)} className="px-3 py-1.5 text-sm bg-yellow-100 text-yellow-700 rounded-lg hover:bg-yellow-200">编辑</button>
        <button onClick={() => handleDeleteVideo(video.id)} disabled={isDeleting === video.id} className="px-3 py-1.5 text-sm bg-red-100 text-red-600 rounded-lg hover:bg-red-200 disabled:opacity-50">{isDeleting === video.id ? <Loader2 className="w-3 h-3 animate-spin" /> : '删除'}</button></div></td></tr>))}</tbody></table></div>}
      </div>
    );
  };

  const renderFans = () => (
    <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm p-4">
      <h3 className="font-bold mb-3">粉丝管理 ({fansCount})</h3>
      {isLoadingFans ? <div className="text-center py-8">加载中...</div>
      : fans.length === 0 ? <div className="text-center py-8">暂无粉丝</div>
      : fans.map((fan) => (<div key={fan.id} className="flex items-center gap-3 py-3 border-b last:border-0"><img src={fan.avatar || 'https://api.dicebear.com/7.x/avataaars/svg?seed=default'} className="w-10 h-10 rounded-full" /><div><p className="font-medium">{fan.name}</p><p className="text-sm text-gray-500">关注于 {new Date(fan.followTime).toLocaleDateString()}</p></div></div>))}
    </div>
  );

  const renderComments = () => (
    <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm p-4">
      <h3 className="font-bold mb-3">评论管理</h3>
      {isLoadingComments ? <div className="text-center py-8">加载中...</div>
      : comments.length === 0 ? <div className="text-center py-8">暂无评论</div>
      : comments.map((comment) => (<div key={comment.id} className="py-3 border-b last:border-0"><div className="flex items-center justify-between"><div className="flex items-center gap-2 mb-1"><img src={comment.userAvatar || 'https://api.dicebear.com/7.x/avataaars/svg?seed=default'} className="w-6 h-6 rounded-full" /><span className="text-sm">{comment.userName}</span><span className="text-xs text-gray-400">{new Date(comment.time).toLocaleDateString()}</span></div><button onClick={() => handleDeleteComment(comment.id)} disabled={isDeletingComment === comment.id} className="px-3 py-1 text-sm bg-red-100 text-red-600 rounded-lg hover:bg-red-200">{isDeletingComment === comment.id ? <Loader2 className="w-3 h-3 animate-spin" /> : '删除'}</button></div><p className="text-sm text-gray-500 mb-1">视频：{comment.videoTitle}</p><p className="font-medium">{comment.content}</p></div>))}
    </div>
  );

  const renderMainContent = () => {
    if (activeTab === 'overview') return renderOverview();
    if (activeTab === 'content') return renderContent();
    if (activeTab === 'fans') return renderFans();
    if (activeTab === 'comments') return renderComments();
    return null;
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* 顶部导航栏 - 包含用户信息和横向菜单 */}
      <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 sticky top-16 z-40">
        <div className="px-4 py-3">
          {/* 用户信息行 */}
          <div className="flex items-center justify-between mb-3 pb-3 border-b border-gray-100 dark:border-gray-700">
            <div className="flex items-center gap-3">
              <img src={user?.avatar || DEFAULT_AVATAR} alt={user?.nickname || '创作者'} className="w-10 h-10 rounded-full" />
              <div>
                <p className="font-medium text-gray-900 dark:text-white">{user?.nickname || '创作者'}</p>
                <p className="text-sm text-gray-500">创作者中心</p>
              </div>
            </div>
          </div>
          
          {/* 横向导航菜单 - 均匀分布 */}
          <div className="flex gap-1 overflow-x-auto">
            {menuItems.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-lg transition-colors whitespace-nowrap ${
                    activeTab === item.id
                      ? 'bg-blue-500 text-white'
                      : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {item.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* 内容区域 */}
      <div className="px-4 py-6">
        <motion.div key={activeTab} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
          {renderMainContent()}
        </motion.div>
      </div>

      {/* 编辑视频弹窗 */}
      {editingVideo && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setEditingVideo(null)}>
          <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-xl font-bold mb-4">编辑视频</h2>
            <div className="space-y-4">
              <div><label className="block text-sm font-medium mb-1">标题</label><input type="text" value={editTitle} onChange={(e) => setEditTitle(e.target.value)} className="w-full px-3 py-2 border rounded-lg" /></div>
              <div><label className="block text-sm font-medium mb-1">简介</label><textarea value={editDescription} onChange={(e) => setEditDescription(e.target.value)} rows={4} className="w-full px-3 py-2 border rounded-lg resize-none" /></div>
              <div><label className="block text-sm font-medium mb-1">分类</label><select value={editCategoryId} onChange={(e) => setEditCategoryId(e.target.value)} className="w-full px-3 py-2 border rounded-lg">{categories.filter(c => c.type === 0 && c.name !== '推荐').map(cat => (<option key={cat.id} value={cat.id}>{cat.name}</option>))}</select></div>
            </div>
            <div className="flex gap-3 mt-6">
              <button onClick={() => setEditingVideo(null)} className="flex-1 px-4 py-2 border rounded-lg hover:bg-gray-50">取消</button>
              <button onClick={handleEditVideo} disabled={isSubmittingEdit} className="flex-1 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50">{isSubmittingEdit ? '保存中...' : '保存'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default CreatorPage;