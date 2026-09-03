import React, { useEffect, useState } from 'react';
import {
  Video,
  Users,
  AlertTriangle,
  Shield,
  CheckCircle,
  XCircle,
  RefreshCw,
  Loader2,
  Eye,
  Radio,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useVideoStore, Video as VideoItem } from '../stores/videoStore';
import { apiRequest } from '../api';

const DEFAULT_COVER_URL =
  'https://images.unsplash.com/photo-1611162616475-46b635cb6868?w=900&auto=format&fit=crop';

const menuItems = [
  { id: 'videos', label: '视频审核', icon: Video },
  { id: 'videoManage', label: '视频管理', icon: Video },
  { id: 'liveManage', label: '直播管理', icon: Radio },
  { id: 'users', label: '用户管理', icon: Users },
  { id: 'reports', label: '举报管理', icon: AlertTriangle },
  { id: 'sensitive', label: '敏感词管理', icon: Shield },
];

function getAuditLabel(status: number) {
  if (status === 1) return '已通过';
  if (status === 2) return '已驳回';
  return '待审核';
}

function getAuditClass(status: number) {
  if (status === 1) return 'bg-green-100 text-green-700';
  if (status === 2) return 'bg-red-100 text-red-700';
  return 'bg-yellow-100 text-yellow-700';
}

function formatDuration(seconds?: number) {
  const safeSeconds = Number(seconds || 0);
  if (!Number.isFinite(safeSeconds) || safeSeconds <= 0) return '0:00';
  const mins = Math.floor(safeSeconds / 60);
  const secs = Math.floor(safeSeconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function getUserTypeText(type: number) {
  if (type === 2) return '管理员';
  if (type === 1) return '创作者';
  return '普通用户';
}

export function AdminPage() {
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState('videos');
  const [pendingVideos, setPendingVideos] = useState<VideoItem[]>([]);
  const [isLoadingVideos, setIsLoadingVideos] = useState(false);
  const [auditingId, setAuditingId] = useState<string | null>(null);
  const [message, setMessage] = useState('');

  const [showRejectModal, setShowRejectModal] = useState(false);
  const [rejectVideoId, setRejectVideoId] = useState<string | null>(null);
  const [rejectReason, setRejectReason] = useState('');

  // 用户管理状态
  const [users, setUsers] = useState<any[]>([]);
  const [isLoadingUsers, setIsLoadingUsers] = useState(false);
  const [userSearchKeyword, setUserSearchKeyword] = useState('');
  const [showUserTypeModal, setShowUserTypeModal] = useState(false);
  const [selectedUser, setSelectedUser] = useState<any>(null);
  const [selectedUserType, setSelectedUserType] = useState(0);

  // 举报管理状态
  const [reports, setReports] = useState<any[]>([]);
  const [isLoadingReports, setIsLoadingReports] = useState(false);
  const [reportFilterStatus, setReportFilterStatus] = useState<number | undefined>(undefined);

  // 敏感词管理状态
  const [sensitiveWords, setSensitiveWords] = useState<{id: number, word: string}[]>([]);
  const [newSensitiveWord, setNewSensitiveWord] = useState('');
  const [isLoadingWords, setIsLoadingWords] = useState(false);

  // 视频管理状态
  const [allVideos, setAllVideos] = useState<any[]>([]);
  const [isLoadingAllVideos, setIsLoadingAllVideos] = useState(false);
  const [videoManagePage, setVideoManagePage] = useState(1);
  const [videoManageHasMore, setVideoManageHasMore] = useState(false);

  // 直播管理状态
  const [liveRooms, setLiveRooms] = useState<any[]>([]);
  const [isLoadingLiveRooms, setIsLoadingLiveRooms] = useState(false);
  const [liveRoomPage, setLiveRoomPage] = useState(1);
  const [liveRoomHasMore, setLiveRoomHasMore] = useState(false);

  // 警告弹窗状态
  const [showWarnModal, setShowWarnModal] = useState(false);
  const [warnTarget, setWarnTarget] = useState<{ type: string; id: string; title: string } | null>(null);
  const [warnReason, setWarnReason] = useState('');

  // 操作弹窗状态（不通过/关闭）
  const [showActionModal, setShowActionModal] = useState(false);
  const [actionTarget, setActionTarget] = useState<{ type: string; id: string; title: string; action: string } | null>(null);
  const [actionReason, setActionReason] = useState('');

  const { fetchPendingVideos, auditVideo } = useVideoStore();

  // 加载待审核视频
  const loadPending = async () => {
    setIsLoadingVideos(true);
    setMessage('');
    try {
      const list = await fetchPendingVideos();
      setPendingVideos(list);
    } catch (error) {
      console.error('加载待审核视频失败:', error);
      setMessage('加载待审核视频失败，请检查后端是否启动。');
    } finally {
      setIsLoadingVideos(false);
    }
  };

  // 加载用户列表
  const loadUsers = async () => {
    setIsLoadingUsers(true);
    try {
      let url = `/api/admin/users?page=1&limit=20`;
      if (userSearchKeyword) url += `&keyword=${encodeURIComponent(userSearchKeyword)}`;
      const data = await apiRequest(url);
      setUsers(data.items || []);
    } catch (error) {
      console.error('获取用户列表失败:', error);
      alert('获取用户列表失败');
    } finally {
      setIsLoadingUsers(false);
    }
  };

  // 加载举报列表
  const loadReports = async () => {
    setIsLoadingReports(true);
    try {
      let url = '/api/admin/reports?page=1&limit=50';
      if (reportFilterStatus !== undefined) url += `&status=${reportFilterStatus}`;
      const data = await apiRequest(url);
      setReports(data.items || []);
    } catch (error) {
      console.error('获取举报列表失败:', error);
    } finally {
      setIsLoadingReports(false);
    }
  };

  // 加载敏感词
  const loadSensitiveWords = async () => {
    setIsLoadingWords(true);
    try {
      const data = await apiRequest('/api/admin/sensitive-words');
      setSensitiveWords(data.items || []);
    } catch (error) {
      console.error('加载敏感词失败:', error);
    } finally {
      setIsLoadingWords(false);
    }
  };

  // 加载所有视频
  const loadAllVideos = async (reset = true) => {
    setIsLoadingAllVideos(true);
    try {
      const pageNum = reset ? 1 : videoManagePage;
      const data = await apiRequest(`/api/admin/videos?page=${pageNum}&limit=20`);
      if (reset) {
        setAllVideos(data.items || []);
      } else {
        setAllVideos(prev => [...prev, ...(data.items || [])]);
      }
      setVideoManageHasMore(data.hasMore || false);
    } catch (error) {
      console.error('加载视频列表失败:', error);
    } finally {
      setIsLoadingAllVideos(false);
    }
  };

  // 加载直播间列表
  const loadLiveRoomsList = async (reset = true) => {
    setIsLoadingLiveRooms(true);
    try {
      const pageNum = reset ? 1 : liveRoomPage;
      const data = await apiRequest(`/api/admin/live-rooms?page=${pageNum}&limit=20`);
      if (reset) {
        setLiveRooms(data.items || []);
      } else {
        setLiveRooms(prev => [...prev, ...(data.items || [])]);
      }
      setLiveRoomHasMore(data.hasMore || false);
    } catch (error) {
      console.error('加载直播间列表失败:', error);
    } finally {
      setIsLoadingLiveRooms(false);
    }
  };

  // 发送警告
  const sendWarn = async () => {
    if (!warnTarget || !warnReason.trim()) return;
    try {
      await apiRequest(`/api/admin/${warnTarget.type}/${warnTarget.id}/warn`, {
        method: 'POST',
        body: JSON.stringify({ reason: warnReason.trim() })
      });
      alert('警告已发送');
      setShowWarnModal(false);
      setWarnReason('');
      setWarnTarget(null);
    } catch (error) {
      console.error('发送警告失败:', error);
      alert('发送失败');
    }
  };

  // 执行操作（不通过/关闭）
  const performAction = async () => {
    if (!actionTarget || !actionReason.trim()) return;
    try {
      const endpoint = actionTarget.action === 'unapprove' 
        ? `/api/admin/videos/${actionTarget.id}/unapprove`
        : `/api/admin/live-rooms/${actionTarget.id}/close`;
      await apiRequest(endpoint, {
        method: 'POST',
        body: JSON.stringify({ reason: actionReason.trim() })
      });
      alert(actionTarget.action === 'unapprove' ? '已设为待审核' : '直播间已关闭');
      setShowActionModal(false);
      setActionReason('');
      setActionTarget(null);
      if (actionTarget.type === 'videos') {
        loadAllVideos(true);
      } else {
        loadLiveRoomsList(true);
      }
    } catch (error) {
      console.error('操作失败:', error);
      alert('操作失败');
    }
  };

  const handleUpdateUserType = async () => {
    if (!selectedUser) return;
    try {
      await apiRequest(`/api/admin/users/${selectedUser.id}/type`, {
        method: 'PATCH',
        body: JSON.stringify({ userType: selectedUserType })
      });
      await loadUsers();
      setShowUserTypeModal(false);
    } catch (error) {
      console.error('修改失败:', error);
      alert('修改失败');
    }
  };

  const handleBanUser = async (user: any) => {
    const newStatus = user.status === 0 ? 1 : 0;
    const action = newStatus === 1 ? '封禁' : '解封';
    if (!confirm(`确定要${action}用户 "${user.nickname}" 吗？`)) return;
    try {
      await apiRequest(`/api/admin/users/${user.id}/ban`, {
        method: 'PATCH',
        body: JSON.stringify({ status: newStatus })
      });
      await loadUsers();
    } catch (error) {
      console.error(`${action}失败:`, error);
      alert(`${action}失败`);
    }
  };

  const handleReport = async (reportId: string, action: 'handle' | 'ignore') => {
    try {
      await apiRequest(`/api/admin/reports/${reportId}/${action}`, { method: 'PATCH' });
      await loadReports();
      alert(action === 'handle' ? '已标记为已处理' : '已忽略');
    } catch (error) {
      console.error('操作失败:', error);
      alert('操作失败');
    }
  };

  const openUserTypeModal = (user: any) => {
    setSelectedUser(user);
    setSelectedUserType(user.userType);
    setShowUserTypeModal(true);
  };

  const addSensitiveWord = async () => {
    if (!newSensitiveWord.trim()) return;
    try {
      await apiRequest('/api/admin/sensitive-words', {
        method: 'POST',
        body: JSON.stringify({ word: newSensitiveWord.trim() })
      });
      setNewSensitiveWord('');
      await loadSensitiveWords();
    } catch (error) {
      console.error('添加失败:', error);
      alert('添加失败');
    }
  };

  const deleteSensitiveWord = async (id: number) => {
    if (!confirm('确定要删除这个敏感词吗？')) return;
    try {
      await apiRequest(`/api/admin/sensitive-words/${id}`, { method: 'DELETE' });
      await loadSensitiveWords();
    } catch (error) {
      console.error('删除失败:', error);
      alert('删除失败');
    }
  };

  useEffect(() => {
    if (activeTab === 'videos') {
      loadPending();
    } else if (activeTab === 'users') {
      loadUsers();
    } else if (activeTab === 'reports') {
      loadReports();
    } else if (activeTab === 'sensitive') {
      loadSensitiveWords();
    } else if (activeTab === 'videoManage') {
      loadAllVideos(true);
    } else if (activeTab === 'liveManage') {
      loadLiveRoomsList(true);
    }
  }, [activeTab, reportFilterStatus]);

  const handleAudit = async (videoId: string, status: number, reason?: string) => {
    setAuditingId(videoId);
    setMessage('');
    try {
      await auditVideo(videoId, status, reason);
      await loadPending();
      setMessage(status === 1 ? '视频已通过审核。' : '视频已驳回。');
      setTimeout(() => setMessage(''), 3000);
    } catch (error) {
      console.error('审核失败:', error);
      setMessage('审核失败，请检查管理员登录状态或后端接口。');
    } finally {
      setAuditingId(null);
    }
  };

  const openRejectModal = (videoId: string) => {
    setRejectVideoId(videoId);
    setRejectReason('');
    setShowRejectModal(true);
  };

  const confirmReject = () => {
    if (rejectVideoId) {
      handleAudit(rejectVideoId, 2, rejectReason);
      setShowRejectModal(false);
      setRejectReason('');
      setRejectVideoId(null);
    }
  };

  const renderVideosTab = () => (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-gray-900 dark:text-white">视频审核</h2>
          <p className="text-sm text-gray-500 mt-1">待审核视频：{pendingVideos.length} 个。</p>
        </div>
        <button onClick={loadPending} disabled={isLoadingVideos} className="flex items-center gap-2 px-3 py-2 bg-white rounded-lg border hover:bg-gray-50">
          {isLoadingVideos ? <Loader2 size={16} className="animate-spin" /> : <RefreshCw size={16} />}刷新
        </button>
      </div>
      {message && <div className="p-3 rounded-lg bg-blue-50 text-blue-700 text-sm">{message}</div>}
      {isLoadingVideos && <div className="p-8 text-center"><Loader2 className="w-8 h-8 animate-spin mx-auto text-blue-500" />加载中...</div>}
      {!isLoadingVideos && pendingVideos.length === 0 && <div className="p-8 text-center text-gray-500">暂无待审核视频</div>}
      {!isLoadingVideos && pendingVideos.map((video) => (
        <div key={video.id} className="flex flex-col md:flex-row gap-4 p-4 bg-white dark:bg-gray-800 rounded-lg shadow-sm">
          <div className="relative w-full md:w-40 aspect-video rounded overflow-hidden bg-gray-200">
            <img src={video.coverUrl || DEFAULT_COVER_URL} alt={video.title} className="w-full h-full object-cover" />
            <span className="absolute bottom-1 right-1 px-1.5 py-0.5 bg-black/70 text-white text-xs rounded">{formatDuration(video.duration)}</span>
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <h3 className="font-medium truncate">{video.title}</h3>
              <span className={`px-2 py-0.5 rounded-full text-xs ${getAuditClass(video.auditStatus)}`}>{getAuditLabel(video.auditStatus)}</span>
            </div>
            <p className="text-sm text-gray-500">上传者：{video.uploaderName}</p>
            <p className="text-sm text-gray-500 line-clamp-2 mt-1">{video.description || '暂无简介'}</p>
          </div>
          <div className="flex gap-2">
            <button onClick={() => navigate(`/video/${video.id}`)} className="p-2 text-blue-600 hover:bg-blue-50 rounded" title="预览"><Eye size={22} /></button>
            <button onClick={() => handleAudit(video.id, 1)} disabled={auditingId === video.id} className="p-2 text-green-600 hover:bg-green-50 rounded" title="通过">
              {auditingId === video.id ? <Loader2 size={22} className="animate-spin" /> : <CheckCircle size={22} />}
            </button>
            <button onClick={() => openRejectModal(video.id)} disabled={auditingId === video.id} className="p-2 text-red-600 hover:bg-red-50 rounded" title="驳回">
              {auditingId === video.id ? <Loader2 size={22} className="animate-spin" /> : <XCircle size={22} />}
            </button>
          </div>
        </div>
      ))}
    </div>
  );

  const renderUsersTab = () => (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold">用户管理</h2>
        <div className="flex gap-2">
          <input type="text" value={userSearchKeyword} onChange={(e) => setUserSearchKeyword(e.target.value)} placeholder="搜索用户..." className="px-3 py-1.5 text-sm border rounded-lg" onKeyDown={(e) => e.key === 'Enter' && loadUsers()} />
          <button onClick={loadUsers} className="px-3 py-1.5 text-sm bg-blue-500 text-white rounded-lg">搜索</button>
        </div>
      </div>
      {isLoadingUsers ? <div className="text-center py-8">加载中...</div> : users.length === 0 ? <div className="text-center py-8 text-gray-500">暂无用户</div> : users.map((user) => (
        <div key={user.id} className="flex items-center justify-between p-4 bg-white dark:bg-gray-800 rounded-lg">
          <div className="flex items-center gap-3">
            <img src={user.avatar} alt={user.nickname} className="w-10 h-10 rounded-full" />
            <div><h3 className="font-medium">{user.nickname}</h3><p className="text-sm text-gray-500">{user.account} · {getUserTypeText(user.userType)}</p></div>
          </div>
          <div className="flex gap-2">
            <button onClick={() => navigate(`/user/${user.id}`)} className="px-3 py-1.5 text-sm bg-gray-100 rounded-lg">查看</button>
            <button onClick={() => openUserTypeModal(user)} className="px-3 py-1.5 text-sm bg-yellow-100 text-yellow-700 rounded-lg">修改类型</button>
            <button onClick={() => handleBanUser(user)} className={`px-3 py-1.5 text-sm rounded-lg ${user.status === 0 ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>
              {user.status === 0 ? '封禁' : '解封'}
            </button>
          </div>
        </div>
      ))}
    </div>
  );

  const renderReportsTab = () => (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold">举报管理</h2>
        <div className="flex gap-2">
          <button onClick={() => setReportFilterStatus(undefined)} className="px-3 py-1 text-sm rounded-lg bg-gray-100">全部</button>
          <button onClick={() => setReportFilterStatus(0)} className="px-3 py-1 text-sm rounded-lg bg-yellow-100">待处理</button>
          <button onClick={() => setReportFilterStatus(1)} className="px-3 py-1 text-sm rounded-lg bg-green-100">已处理</button>
          <button onClick={() => setReportFilterStatus(2)} className="px-3 py-1 text-sm rounded-lg bg-gray-100">已忽略</button>
        </div>
      </div>
      {isLoadingReports ? <div className="text-center py-8">加载中...</div> : reports.length === 0 ? <div className="text-center py-8 text-gray-500">暂无举报</div> : reports.map((report) => (
        <div key={report.id} className="p-4 bg-white dark:bg-gray-800 rounded-lg">
          <div className="flex justify-between items-start">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <img src={report.reporterAvatar} className="w-6 h-6 rounded-full" />
                <span className="font-medium">{report.reporterName}</span>
                <span className="text-xs text-gray-400">{new Date(report.createdAt).toLocaleString()}</span>
                <span className={`px-2 py-0.5 text-xs rounded-full ${report.status === 0 ? 'bg-yellow-100 text-yellow-700' : report.status === 1 ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'}`}>
                  {report.status === 0 ? '待处理' : report.status === 1 ? '已处理' : '已忽略'}
                </span>
              </div>
              <p className="text-sm text-gray-600">举报对象: {report.targetType === 0 ? '视频' : report.targetType === 1 ? '评论' : '直播'}</p>
              <p className="text-sm font-medium mb-2">{report.targetInfo?.title || report.targetInfo?.content || '已删除'}</p>
              <p className="text-sm text-gray-500">理由：{report.reason}</p>
            </div>
            <div className="flex gap-2 ml-4">
              <button 
                onClick={() => {
                  if (report.targetType === 0) {
                    window.open(`/#/video/${report.targetId}`, '_blank');
                  } else if (report.targetType === 1) {
                    const videoId = report.videoId || report.targetUrl?.split('/video/')[1]?.split('#')[0] || report.targetId;
                    window.open(`/#/video/${videoId}`, '_blank');
                  } else if (report.targetType === 2) {
                    window.open(`/#/live/${report.targetId}`, '_blank');
                  }
                }}
                className="px-3 py-1 text-sm bg-blue-100 text-blue-700 rounded-lg"
              >
                查看来源
              </button>
              {report.status === 0 && (
                <>
                  <button onClick={() => handleReport(report.id, 'handle')} className="px-3 py-1 text-sm bg-green-100 text-green-700 rounded-lg">已处理</button>
                  <button onClick={() => handleReport(report.id, 'ignore')} className="px-3 py-1 text-sm bg-gray-100 text-gray-700 rounded-lg">忽略</button>
                </>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  );

  const renderSensitiveTab = () => (
    <div className="space-y-4">
      <h2 className="text-lg font-bold text-gray-900 dark:text-white">敏感词管理</h2>
      <div className="flex gap-2">
        <input
          value={newSensitiveWord}
          onChange={(e) => setNewSensitiveWord(e.target.value)}
          placeholder="输入敏感词"
          className="flex-1 px-4 py-2 border rounded-lg dark:bg-gray-800"
          onKeyDown={(e) => e.key === 'Enter' && addSensitiveWord()}
        />
        <button onClick={addSensitiveWord} className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600">添加</button>
      </div>
      {isLoadingWords ? (
        <div className="text-center py-8 text-gray-500">加载中...</div>
      ) : sensitiveWords.length === 0 ? (
        <div className="text-center py-8 text-gray-500">暂无敏感词</div>
      ) : (
        <div className="space-y-2">
          {sensitiveWords.map((word) => (
            <div key={word.id} className="flex items-center justify-between p-3 bg-white dark:bg-gray-800 rounded-lg border">
              <span className="font-medium text-gray-900 dark:text-white">{word.word}</span>
              <button onClick={() => deleteSensitiveWord(word.id)} className="text-red-500 hover:text-red-700">删除</button>
            </div>
          ))}
        </div>
      )}
      <p className="text-sm text-gray-500 mt-4">包含敏感词的内容会被自动替换为 * 号。</p>
    </div>
  );

  const renderVideoManageTab = () => (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold">视频管理</h2>
        <button onClick={() => loadAllVideos(true)} className="px-3 py-1 text-sm bg-gray-100 rounded-lg">刷新</button>
      </div>
      {isLoadingAllVideos && allVideos.length === 0 ? (
        <div className="text-center py-8">加载中...</div>
      ) : allVideos.length === 0 ? (
        <div className="text-center py-8 text-gray-500">暂无视频</div>
      ) : (
        <div className="space-y-3">
          {allVideos.map((video) => (
            <div key={video.id} className="flex items-center justify-between p-4 bg-white dark:bg-gray-800 rounded-lg">
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{video.title}</span>
                  <span className={`px-2 py-0.5 text-xs rounded-full ${video.auditStatus === 1 ? 'bg-green-100 text-green-700' : video.auditStatus === 2 ? 'bg-red-100 text-red-700' : 'bg-yellow-100 text-yellow-700'}`}>
                    {video.auditStatus === 1 ? '已通过' : video.auditStatus === 2 ? '已驳回' : '待审核'}
                  </span>
                </div>
                <p className="text-sm text-gray-500">上传者：{video.uploaderName} | 播放量：{video.viewCount}</p>
              </div>
              <div className="flex gap-2">
                <button onClick={() => window.open(`/#/video/${video.id}`, '_blank')} className="px-3 py-1 text-sm bg-blue-100 text-blue-700 rounded-lg">查看</button>
                <button onClick={() => { setWarnTarget({ type: 'videos', id: video.id, title: video.title }); setShowWarnModal(true); }} className="px-3 py-1 text-sm bg-yellow-100 text-yellow-700 rounded-lg">警告</button>
                <button onClick={() => { setActionTarget({ type: 'videos', id: video.id, title: video.title, action: 'unapprove' }); setShowActionModal(true); }} className="px-3 py-1 text-sm bg-red-100 text-red-700 rounded-lg">设为待审核</button>
              </div>
            </div>
          ))}
          {videoManageHasMore && (
            <button onClick={() => { setVideoManagePage(prev => prev + 1); loadAllVideos(false); }} className="w-full py-2 text-center text-blue-500">加载更多</button>
          )}
        </div>
      )}
    </div>
  );

  const renderLiveManageTab = () => (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold">直播管理</h2>
        <button onClick={() => loadLiveRoomsList(true)} className="px-3 py-1 text-sm bg-gray-100 rounded-lg">刷新</button>
      </div>
      {isLoadingLiveRooms && liveRooms.length === 0 ? (
        <div className="text-center py-8">加载中...</div>
      ) : liveRooms.length === 0 ? (
        <div className="text-center py-8 text-gray-500">暂无直播间</div>
      ) : (
        <div className="space-y-3">
          {liveRooms.map((room) => (
            <div key={room.id} className="flex items-center justify-between p-4 bg-white dark:bg-gray-800 rounded-lg">
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{room.title}</span>
                  <span className={`px-2 py-0.5 text-xs rounded-full ${room.status === 1 ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-700'}`}>
                    {room.status === 1 ? '直播中' : '已结束'}
                  </span>
                </div>
                <p className="text-sm text-gray-500">主播：{room.anchorName} | 在线：{room.onlineCount}</p>
              </div>
              <div className="flex gap-2">
                <button onClick={() => window.open(`/#/live/${room.id}`, '_blank')} className="px-3 py-1 text-sm bg-blue-100 text-blue-700 rounded-lg">查看</button>
                <button onClick={() => { setWarnTarget({ type: 'live-rooms', id: room.id, title: room.title }); setShowWarnModal(true); }} className="px-3 py-1 text-sm bg-yellow-100 text-yellow-700 rounded-lg">警告</button>
                <button onClick={() => { setActionTarget({ type: 'live-rooms', id: room.id, title: room.title, action: 'close' }); setShowActionModal(true); }} className="px-3 py-1 text-sm bg-red-100 text-red-700 rounded-lg">关闭</button>
              </div>
            </div>
          ))}
          {liveRoomHasMore && (
            <button onClick={() => { setLiveRoomPage(prev => prev + 1); loadLiveRoomsList(false); }} className="w-full py-2 text-center text-blue-500">加载更多</button>
          )}
        </div>
      )}
    </div>
  );

  const renderContent = () => {
    switch (activeTab) {
      case 'videos': return renderVideosTab();
      case 'users': return renderUsersTab();
      case 'reports': return renderReportsTab();
      case 'sensitive': return renderSensitiveTab();
      case 'videoManage': return renderVideoManageTab();
      case 'liveManage': return renderLiveManageTab();
      default: return null;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="max-w-7xl mx-auto px-4 py-6">
        <h1 className="text-2xl font-bold mb-6">管理后台</h1>
        
        {/* 横向导航菜单 - 撑满 */}
        <div className="flex flex-wrap gap-1 mb-6 border-b border-gray-200 dark:border-gray-700">
          {menuItems.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={`flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-t-lg transition-colors ${
                  activeTab === item.id
                    ? 'bg-blue-500 text-white'
                    : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800'
                }`}
              >
                <Icon size={18} />
                {item.label}
              </button>
            );
          })}
        </div>

        {/* 内容区域 */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm p-4">
          {renderContent()}
        </div>
      </div>

      {/* 驳回理由弹窗 */}
      {showRejectModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowRejectModal(false)}>
          <div className="bg-white rounded-2xl p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-xl font-bold mb-4">驳回视频</h2>
            <textarea value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} rows={4} className="w-full px-4 py-2 border rounded-lg resize-none" placeholder="请输入驳回理由..." />
            <div className="flex gap-3 mt-4">
              <button onClick={() => setShowRejectModal(false)} className="flex-1 px-4 py-2 border rounded-lg">取消</button>
              <button onClick={confirmReject} className="flex-1 px-4 py-2 bg-red-500 text-white rounded-lg">确认驳回</button>
            </div>
          </div>
        </div>
      )}

      {/* 修改用户类型弹窗 */}
      {showUserTypeModal && selectedUser && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowUserTypeModal(false)}>
          <div className="bg-white rounded-2xl p-6 w-full max-w-sm" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-xl font-bold mb-4">修改用户类型</h2>
            <p className="text-sm text-gray-500 mb-4">用户：{selectedUser.nickname} ({selectedUser.account})</p>
            <select value={selectedUserType} onChange={(e) => setSelectedUserType(Number(e.target.value))} className="w-full px-4 py-2 border rounded-lg mb-4">
              <option value={0}>普通用户</option><option value={1}>创作者</option><option value={2}>管理员</option>
            </select>
            <div className="flex gap-3">
              <button onClick={() => setShowUserTypeModal(false)} className="flex-1 px-4 py-2 border rounded-lg">取消</button>
              <button onClick={handleUpdateUserType} className="flex-1 px-4 py-2 bg-blue-500 text-white rounded-lg">确认</button>
            </div>
          </div>
        </div>
      )}

      {/* 警告弹窗 */}
      {showWarnModal && warnTarget && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowWarnModal(false)}>
          <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-xl font-bold mb-4">发送警告</h2>
            <p className="text-sm text-gray-500 mb-4">对象：{warnTarget.title}</p>
            <textarea value={warnReason} onChange={(e) => setWarnReason(e.target.value)} rows={4} className="w-full px-4 py-2 border rounded-lg resize-none" placeholder="请输入警告内容..." />
            <div className="flex gap-3 mt-4">
              <button onClick={() => setShowWarnModal(false)} className="flex-1 px-4 py-2 border rounded-lg">取消</button>
              <button onClick={sendWarn} className="flex-1 px-4 py-2 bg-yellow-500 text-white rounded-lg">发送警告</button>
            </div>
          </div>
        </div>
      )}

      {/* 操作弹窗（不通过/关闭） */}
      {showActionModal && actionTarget && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowActionModal(false)}>
          <div className="bg-white dark:bg-gray-800 rounded-2xl p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-xl font-bold mb-4">{actionTarget.action === 'unapprove' ? '设为待审核' : '关闭直播间'}</h2>
            <p className="text-sm text-gray-500 mb-4">对象：{actionTarget.title}</p>
            <textarea value={actionReason} onChange={(e) => setActionReason(e.target.value)} rows={4} className="w-full px-4 py-2 border rounded-lg resize-none" placeholder="请输入理由..." />
            <div className="flex gap-3 mt-4">
              <button onClick={() => setShowActionModal(false)} className="flex-1 px-4 py-2 border rounded-lg">取消</button>
              <button onClick={performAction} className="flex-1 px-4 py-2 bg-red-500 text-white rounded-lg">{actionTarget.action === 'unapprove' ? '确认' : '关闭'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default AdminPage;