import { create } from 'zustand';
import { apiRequest } from '../api';

const DEFAULT_VIDEO_URL = '/demo-videos/This-is-beihang.mp4';
const DEFAULT_COVER_URL =
  'https://images.unsplash.com/photo-1611162616475-46b635cb6868?w=900&auto=format&fit=crop';

function normalizeVideo(v: any): Video {
  const duration =
    typeof v.duration === 'number'
      ? v.duration
      : Number(v.duration) || 596;

  const tags = Array.isArray(v.tags)
    ? v.tags
    : typeof v.tags === 'string'
      ? v.tags.split(',').filter(Boolean)
      : [];

  return {
    id: String(v.id || 'mock-video-1'),
    title: v.title || '未命名视频',
    description: v.description || '',
    tags,
    coverUrl: v.coverUrl || v.cover_url || DEFAULT_COVER_URL,
    videoUrl: v.videoUrl || v.video_url || DEFAULT_VIDEO_URL,
    duration,
    categoryId: String(v.categoryId || v.category_id || '1'),
    categoryName: v.categoryName || v.category_name || '推荐',

    viewCount: Number(v.viewCount ?? v.view_count ?? v.views ?? 0),
    likeCount: Number(v.likeCount ?? v.like_count ?? v.likes ?? 0),
    commentCount: Number(v.commentCount ?? v.comment_count ?? 0),
    favoriteCount: Number(v.favoriteCount ?? v.favorite_count ?? v.favorites ?? 0),

    uploaderId: String(v.uploaderId || v.uploader_id || v.authorId || v.author_id || ''),
    uploaderName:
      v.uploaderName ||
      v.uploader_name ||
      v.authorName ||
      v.author_name ||
      v.author?.nickname ||
      '创作者小明',
    uploaderAvatar:
      v.uploaderAvatar ||
      v.uploader_avatar ||
      v.authorAvatar ||
      v.author_avatar ||
      v.author?.avatar ||
      'https://api.dicebear.com/7.x/avataaars/svg?seed=creator',

    uploadTime:
      v.uploadTime ||
      v.upload_time ||
      v.createdAt ||
      v.created_at ||
      new Date().toISOString(),

    auditStatus: Number(v.auditStatus ?? v.audit_status ?? 1),
  };
}

function normalizeComment(c: any): Comment {
  return {
    id: String(c.id || Math.random()),
    content: c.content || '',
    userId: String(c.userId || c.user_id || ''),
    username:
      c.username ||
      c.userName ||
      c.user_name ||
      c.user?.nickname ||
      'xuyue',
    userAvatar:
      c.userAvatar ||
      c.user_avatar ||
      c.user?.avatar ||
      'https://api.dicebear.com/7.x/avataaars/svg?seed=user',
    videoId: String(c.videoId || c.video_id || ''),
    parentId: String(c.parentId || c.parent_id || '0'),
    likeCount: Number(c.likeCount ?? c.like_count ?? c.likes ?? 0),
    isTop: Boolean(c.isTop ?? c.is_top ?? false),
    createTime:
      c.createTime ||
      c.create_time ||
      c.createdAt ||
      c.created_at ||
      new Date().toISOString(),
    replies: c.replies || [],
    replyToUserId: String(c.replyToUserId || c.reply_to_user_id || ''),
    replyToUsername: c.replyToUsername || c.reply_to_username || '',
    replyCount: Number(c.replyCount ?? c.reply_count ?? 0),
  };
}

function normalizeDanmaku(d: any): Danmaku {
  return {
    id: String(d.id || Math.random()),
    content: d.content || '',
    color: d.color || '#ffffff',
    position: Number(d.position ?? 0),
    userId: String(d.userId || d.user_id || ''),
    username:
      d.username ||
      d.userName ||
      d.user_name ||
      d.user?.nickname ||
      'xuyue',
    videoTime: Number(
      d.videoTime ??
      d.video_time ??
      d.timePoint ??
      d.time_point ??
      0
    ),
    sendTime:
      d.sendTime ||
      d.send_time ||
      d.createdAt ||
      d.created_at ||
      new Date().toISOString(),
  };
}

function getListFromResponse(data: any) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.items)) return data.items;
  if (Array.isArray(data?.data)) return data.data;
  return [];
}

export interface Video {
  id: string;
  title: string;
  description: string;
  tags: string[];
  coverUrl: string;
  videoUrl: string;
  duration: number;
  categoryId: string;
  categoryName: string;
  viewCount: number;
  likeCount: number;
  commentCount: number;
  favoriteCount: number;
  uploaderId: string;
  uploaderName: string;
  uploaderAvatar: string;
  uploadTime: string;
  auditStatus: number;
}

export interface Comment {
  id: string;
  content: string;
  userId: string;
  username: string;
  userAvatar: string;
  videoId: string;
  parentId: string;
  likeCount: number;
  isTop: boolean;
  createTime: string;
  replies?: Comment[];
  replyToUserId?: string;
  replyToUsername?: string;
  replyCount?: number;
}

export interface Danmaku {
  id: string;
  content: string;
  color: string;
  position: number;
  userId: string;
  username: string;
  videoTime: number;
  sendTime: string;
}

export interface Category {
  id: string;
  name: string;
  type: number;
}

interface VideoStore {
  videos: Video[];
  currentVideo: Video | null;
  comments: Comment[];
  danmakuList: Danmaku[];
  relatedVideos: Video[];
  categories: Category[];
  searchResults: Video[];
  searchKeyword: string;
  isLoading: boolean;
  hasMore: boolean;
  page: number;

  fetchVideos: (params?: any) => Promise<void>;
  fetchVideoById: (id: string) => Promise<Video | null>;
  fetchVideoDetail: (id: string) => Promise<void>;
  fetchComments: (videoId: string) => Promise<void>;
  fetchDanmaku: (videoId: string) => Promise<void>;
  fetchRelatedVideos: (videoId: string) => Promise<void>;
  fetchCategories: () => Promise<void>;
  searchVideos: (keyword: string, sort?: string) => Promise<void>;
  likeVideo: (videoId: string) => Promise<void>;
  favoriteVideo: (videoId: string) => Promise<void>;
  addComment: (videoId: string, content: string, parentId?: string, replyToUserId?: string) => Promise<void>;
  fetchReplies: (parentCommentId: string) => Promise<void>;
  sendDanmaku: (
    videoId: string,
    content: string,
    color?: string,
    videoTime?: number
  ) => Promise<void>;
  uploadVideo: (videoData: any) => Promise<boolean>;
  fetchPendingVideos: () => Promise<Video[]>;
  auditVideo: (videoId: string, auditStatus: number) => Promise<void>;
  fetchCreatorVideos: () => Promise<Video[]>;
  loadMore: () => Promise<void>;
}
const fallbackCategories: Category[] = [
  { id: '0', name: '推荐', type: 0 },
  { id: '1', name: '游戏', type: 0 },
  { id: '2', name: '音乐', type: 0 },
  { id: '3', name: '影视', type: 0 },
  { id: '4', name: '科技', type: 0 },
  { id: '5', name: '生活', type: 0 },
  { id: '6', name: '游戏直播', type: 1 },
  { id: '7', name: '娱乐直播', type: 1 },
  { id: '8', name: '学习直播', type: 1 }
];

export const useVideoStore = create<VideoStore>((set, get) => ({  videos: [],
  currentVideo: null,
  comments: [],
  danmakuList: [],
  relatedVideos: [],
  categories: fallbackCategories,
  searchResults: [],
  searchKeyword: '',
  isLoading: false,
  hasMore: true,
  page: 1,

  fetchVideos: async (params?: any) => {
  set({ isLoading: true });

  try {
    const query = new URLSearchParams();

    if (params?.keyword) {
      query.set('keyword', String(params.keyword));
    }

    if (params?.categoryId && String(params.categoryId) !== '0') {
      query.set('category_id', String(params.categoryId));
    }

    if (params?.sort) {
      query.set('sort', String(params.sort));
    }

    if (params?.page) {
      query.set('page', String(params.page));
    }

    const url = query.toString()
      ? `/api/videos?${query.toString()}`
      : '/api/videos';

    const data: any = await apiRequest(url);
    const list = getListFromResponse(data);

    set({
      videos: list.map(normalizeVideo),
      hasMore: Boolean(data?.hasMore ?? data?.has_more ?? false),
      isLoading: false,
    });
  } catch (error) {
    console.error('获取视频列表失败:', error);

    set({
      videos: [
        normalizeVideo({
          id: 1,
          title: 'Big Buck Bunny 动画短片',
          description: '后端未连接时显示的前端固定模拟视频。',
          coverUrl: 'https://peach.blender.org/wp-content/uploads/title_anouncement.jpg?x11217',
          videoUrl: DEFAULT_VIDEO_URL,
          duration: 596,
          tags: ['动画', '短片'],
          viewCount: 12800,
          likeCount: 860,
          favoriteCount: 320,
          commentCount: 3,
          uploaderName: '创作者小明',
          uploaderAvatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=creator',
          uploadTime: new Date().toISOString(),
        }),
      ],
      hasMore: false,
      isLoading: false,
    });
  }
},
  fetchVideoById: async (id: string) => {
  try {
    const data: any = await apiRequest(`/api/videos/${id}`);
    const video = normalizeVideo(data);

    set({
      currentVideo: video,
    });

    return video;
  } catch (error) {
    console.error('获取视频详情失败:', error);

    const fallbackVideo = normalizeVideo({
      id,
      title: 'Big Buck Bunny 动画短片',
      description: '当前显示的是固定模拟视频，用于保证播放器可以正常展示。',
      coverUrl: 'https://peach.blender.org/wp-content/uploads/title_anouncement.jpg?x11217',
      videoUrl: DEFAULT_VIDEO_URL,
      duration: 596,
      tags: ['动画', '短片'],
      viewCount: 12800,
      likeCount: 860,
      favoriteCount: 320,
      commentCount: 3,
      uploaderName: '创作者小明',
      uploaderAvatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=creator',
      uploadTime: new Date().toISOString(),
    });

    set({
      currentVideo: fallbackVideo,
    });

    return fallbackVideo;
  }
},

  fetchVideoDetail: async (id: string) => {
  set({ isLoading: true });

  try {
    const data: any = await apiRequest(`/api/videos/${id}`);
    const video = normalizeVideo(data);

    set({
      currentVideo: video,
      isLoading: false,
    });
  } catch (error) {
    console.error('获取视频详情失败', error);

    const fallbackVideo = normalizeVideo({
      id,
      title: 'Big Buck Bunny 动画短片',
      description: '当前显示的是固定模拟视频，用于保证播放器可以正常展示。',
      coverUrl: 'https://peach.blender.org/wp-content/uploads/title_anouncement.jpg?x11217',
      videoUrl: DEFAULT_VIDEO_URL,
      duration: 596,
      tags: ['动画', '短片'],
      viewCount: 12800,
      likeCount: 860,
      favoriteCount: 320,
      commentCount: 2,
      uploaderName: '创作者小明',
      uploaderAvatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=creator',
      uploadTime: new Date().toISOString(),
    });

    set({
      currentVideo: fallbackVideo,
      isLoading: false,
    });
  }
},

  fetchReplies: async (parentCommentId: string) => {
    try {
      const data: any = await apiRequest(`/api/comments/${parentCommentId}/replies`);
      const list = Array.isArray(data) ? data : [];
      const replies = list.map(normalizeComment);
      set((state) => ({
        comments: state.comments.map((c) =>
          c.id === parentCommentId ? { ...c, replies } : c
        ),
      }));
    } catch (e) {
      console.error('加载回复失败:', e);
    }
  },

  fetchComments: async (videoId: string) => {
  try {
    const data: any = await apiRequest(`/api/videos/${videoId}/comments`);
    const list = getListFromResponse(data);

    set({
      comments: list.map(normalizeComment),
    });
  } catch (error) {
    console.error('获取评论失败:', error);

    set({
      comments: [
        normalizeComment({
          id: 1,
          videoId,
          userId: 1,
          username: 'xuyue',
          userAvatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=user',
          content: '这个视频可以正常播放，评论区也有内容显示。',
          likeCount: 18,
          createTime: new Date().toISOString(),
        }),
        normalizeComment({
          id: 2,
          videoId,
          userId: 2,
          username: '创作者小明',
          userAvatar: 'https://api.dicebear.com/7.x/avataaars/svg?seed=creator',
          content: '这是固定模拟评论，用于作业展示。',
          likeCount: 9,
          createTime: new Date().toISOString(),
        }),
      ],
    });
  }
},

  fetchDanmaku: async (videoId: string) => {
  try {
    const data: any = await apiRequest(`/api/videos/${videoId}/danmaku`);
    const list = getListFromResponse(data);

    set({
      danmakuList: list.map(normalizeDanmaku),
    });
  } catch (error) {
    console.error('获取弹幕失败:', error);

    set({
      danmakuList: [
        normalizeDanmaku({
          id: 1,
          videoId,
          userId: 1,
          username: 'xuyue',
          content: '来了来了！',
          videoTime: 2,
          color: '#ffffff',
          position: 0,
        }),
        normalizeDanmaku({
          id: 2,
          videoId,
          userId: 1,
          username: 'xuyue',
          content: '这个视频终于能播放了',
          videoTime: 5,
          color: '#ff4d4f',
          position: 0,
        }),
        normalizeDanmaku({
          id: 3,
          videoId,
          userId: 2,
          username: '创作者小明',
          content: '作业展示效果不错',
          videoTime: 8,
          color: '#00d4ff',
          position: 0,
        }),
      ],
    });
  }
},

  fetchRelatedVideos: async (videoId: string) => {
      try {
        const data: any = await apiRequest(`/api/videos/${videoId}/related`);
        const list = getListFromResponse(data);

        set({
          relatedVideos: list.map(normalizeVideo),
        });
      } catch (error) {
        console.error('获取相关推荐失败', error);
        set({ relatedVideos: [] });
      }
    },

  fetchCategories: async () => {
  try {
    const data: any = await apiRequest('/api/categories');

    const list = Array.isArray(data)
      ? data
      : Array.isArray(data?.items)
        ? data.items
        : fallbackCategories;

    set({
      categories: list.map((item: any) => ({
        id: String(item.id),
        name: item.name,
        type: Number(item.type ?? 0),
      })),
    });
  } catch (error) {
    console.error('获取分类失败，使用本地默认分类', error);
    set({ categories: fallbackCategories });
  }
},

  searchVideos: async (keyword: string, sort = 'comprehensive') => {
      set({ isLoading: true, searchKeyword: keyword });

      try {
        const query = new URLSearchParams({ keyword, sort });
        const data: any = await apiRequest(`/api/videos?${query.toString()}`);
        const list = getListFromResponse(data);

        set({
          searchResults: list.map(normalizeVideo),
          isLoading: false,
        });
      } catch (error) {
        console.error('搜索失败', error);

        set({
          searchResults: [],
          isLoading: false,
        });
      }
    },

  likeVideo: async (videoId: string) => {
      try {
        const data: any = await apiRequest(`/api/videos/${videoId}/like`, {
          method: 'POST',
        });

        const video = normalizeVideo(data);

        set((state) => ({
          currentVideo:
            state.currentVideo?.id === videoId ? video : state.currentVideo,
          videos: state.videos.map((v) => (v.id === videoId ? video : v)),
          searchResults: state.searchResults.map((v) =>
            v.id === videoId ? video : v
          ),
          relatedVideos: state.relatedVideos.map((v) =>
            v.id === videoId ? video : v
          ),
        }));
      } catch (error) {
        console.error('点赞失败', error);

        // 后端失败时，前端也临时 +1，保证演示时有反馈
        set((state) => ({
          currentVideo:
            state.currentVideo?.id === videoId
              ? {
                  ...state.currentVideo,
                  likeCount: state.currentVideo.likeCount + 1,
                }
              : state.currentVideo,
          videos: state.videos.map((v) =>
            v.id === videoId ? { ...v, likeCount: v.likeCount + 1 } : v
          ),
        }));
      }
    },

  favoriteVideo: async (videoId: string) => {
      try {
        const data: any = await apiRequest(`/api/videos/${videoId}/favorite`, {
          method: 'POST',
        });

        const video = normalizeVideo(data);

        set((state) => ({
          currentVideo:
            state.currentVideo?.id === videoId ? video : state.currentVideo,
          videos: state.videos.map((v) => (v.id === videoId ? video : v)),
        }));
      } catch (error) {
        console.error('收藏失败', error);

        // 后端失败时，前端临时 +1，保证演示时有反馈
        set((state) => ({
          currentVideo:
            state.currentVideo?.id === videoId
              ? {
                  ...state.currentVideo,
                  favoriteCount: state.currentVideo.favoriteCount + 1,
                }
              : state.currentVideo,
          videos: state.videos.map((v) =>
            v.id === videoId
              ? { ...v, favoriteCount: v.favoriteCount + 1 }
              : v
          ),
        }));
      }
    },

  addComment: async (
    videoId: string,
    content: string,
    parentId: string = '0',
    replyToUserId: string = '',
  ) => {
  try {
    const data: any = await apiRequest(`/api/videos/${videoId}/comments`, {
      method: 'POST',
      body: JSON.stringify({ content, parentId, replyToUserId }),
    });

    const newComment = normalizeComment(data);

    set((state) => {
      // 回复:挂到父评论的 replies 里,并 +1 计数
      if (newComment.parentId && newComment.parentId !== '0') {
        return {
          comments: state.comments.map((c) =>
            c.id === newComment.parentId
              ? {
                  ...c,
                  replies: [...(c.replies || []), newComment],
                  replyCount: (c.replyCount || 0) + 1,
                }
              : c
          ),
        };
      }
      return { comments: [newComment, ...state.comments] };
    });
  } catch (error) {
    console.error('发表评论失败:', error);
  }
},

  sendDanmaku: async (
  videoId: string,
  content: string,
  color: string = '#ffffff',
  videoTime: number = 0
) => {
  try {
    const data: any = await apiRequest(`/api/videos/${videoId}/danmaku`, {
      method: 'POST',
      body: JSON.stringify({
        content,
        color,
        position: 0,
        videoTime,
      }),
    });

    const newDanmaku = normalizeDanmaku(data);

    set((state) => ({
      danmakuList: [...state.danmakuList, newDanmaku],
    }));
  } catch (error) {
    console.error('发送弹幕失败:', error);

    const mockDanmaku = normalizeDanmaku({
      id: Date.now(),
      videoId,
      userId: 1,
      username: 'xuyue',
      content,
      color,
      position: 0,
      videoTime,
      sendTime: new Date().toISOString(),
    });

    set((state) => ({
      danmakuList: [...state.danmakuList, mockDanmaku],
    }));
  }
},

  uploadVideo: async (videoData: any) => {
  try {
    const payload = {
      title: videoData.title || '未命名视频',
      description: videoData.description || '这是一个由创作者上传的视频。',
      tags: Array.isArray(videoData.tags)
        ? videoData.tags
        : typeof videoData.tags === 'string'
          ? videoData.tags.split(',').filter(Boolean)
          : ['投稿', '视频'],
      coverUrl: videoData.coverUrl || videoData.cover_url || DEFAULT_COVER_URL,
      videoUrl: videoData.videoUrl || videoData.video_url || DEFAULT_VIDEO_URL,
      duration: Number(videoData.duration) || 596,
      categoryId: String(videoData.categoryId || videoData.category_id || '1'),
    };

    const data: any = await apiRequest('/api/videos', {
      method: 'POST',
      body: JSON.stringify(payload),
    });

    return Boolean(data);
  } catch (error) {
    console.error('上传视频失败:', error);
    return false;
  }
},
  fetchPendingVideos: async () => {
  try {
    const data: any = await apiRequest('/api/admin/videos/pending');
    const list = getListFromResponse(data);

    return list.map(normalizeVideo);
  } catch (error) {
    console.error('获取待审核视频失败', error);
    return [];
  }
},

  auditVideo: async (videoId: string, auditStatus: number) => {
  try {
    await apiRequest(`/api/admin/videos/${videoId}/audit`, {
      method: 'PATCH',
      body: JSON.stringify({ auditStatus }),
    });
  } catch (error) {
    console.error('审核视频失败:', error);
    throw error;
  }
},

  fetchCreatorVideos: async () => {
  try {
    const data: any = await apiRequest('/api/creator/videos');
    const list = getListFromResponse(data);

    return list.map(normalizeVideo);
  } catch (error) {
    console.error('获取创作者视频失败', error);
    return [];
  }
},

loadMore: async () => {
  const { page, hasMore, isLoading } = get();

  if (!hasMore || isLoading) return;

  await get().fetchVideos({ page: page + 1 });

  set({ page: page + 1 });
},
}));
