import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { apiRequest } from '../api';

const DEFAULT_AVATAR =
  'https://api.dicebear.com/7.x/avataaars/svg?seed=user';

export interface User {
  id: string;
  account: string;
  nickname: string;
  avatar: string;
  bio: string;
  userType: number; // 0普通用户，1创作者，2管理员
  status: number;
  streamKey?: string;
}

interface AuthState {
  token: string | null;
  user: User | null;
  isLoggedIn: boolean;
  showLoginModal: boolean;
  showRegisterModal: boolean;

  login: (account: string, password: string) => Promise<boolean>;
  register: (
    account: string,
    password: string,
    nickname: string
  ) => Promise<boolean>;
  logout: () => void;

  openLoginModal: () => void;
  closeLoginModal: () => void;
  openRegisterModal: () => void;
  closeRegisterModal: () => void;

  updateUser: (user: Partial<User>) => Promise<void>;
  refreshMe: () => Promise<void>;
  upgradeToCreator: () => Promise<boolean>;
}

function normalizeUser(user: any): User {
  return {
    id: String(user?.id || ''),
    account: user?.account || '',
    nickname: user?.nickname || user?.name || '用户',
    avatar: user?.avatar || DEFAULT_AVATAR,
    bio: user?.bio || '',
    userType: Number(user?.userType ?? user?.user_type ?? 0),
    status: Number(user?.status ?? 0),
    streamKey: user?.streamKey || user?.stream_key,
  };
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      isLoggedIn: false,
      showLoginModal: false,
      showRegisterModal: false,

      login: async (account: string, password: string) => {
        try {
          const data: any = await apiRequest('/api/auth/login', {
            method: 'POST',
            body: JSON.stringify({
              account: account.trim(),
              password,
            }),
          });

          const token = data?.token || '';
          const user = normalizeUser(data?.user);

          if (!token || !user.id) {
            throw new Error('登录返回数据不完整');
          }

          set({
            token,
            user,
            isLoggedIn: true,
            showLoginModal: false,
            showRegisterModal: false,
          });

          return true;
        } catch (error) {
          console.error('登录失败:', error);

          set({
            token: null,
            user: null,
            isLoggedIn: false,
          });

          return false;
        }
      },

      register: async (
        account: string,
        password: string,
        nickname: string
      ) => {
        try {
          const data: any = await apiRequest('/api/auth/register', {
            method: 'POST',
            body: JSON.stringify({
              account: account.trim(),
              password,
              nickname: nickname.trim() || account.trim(),
            }),
          });

          const token = data?.token || '';
          const user = normalizeUser(data?.user);

          if (!token || !user.id) {
            throw new Error('注册返回数据不完整');
          }

          set({
            token,
            user,
            isLoggedIn: true,
            showLoginModal: false,
            showRegisterModal: false,
          });

          return true;
        } catch (error) {
          console.error('注册失败:', error);

          set({
            token: null,
            user: null,
            isLoggedIn: false,
          });

          return false;
        }
      },

      logout: () => {
        set({
          token: null,
          user: null,
          isLoggedIn: false,
          showLoginModal: false,
          showRegisterModal: false,
        });
      },

      openLoginModal: () => {
        set({
          showLoginModal: true,
          showRegisterModal: false,
        });
      },

      closeLoginModal: () => {
        set({
          showLoginModal: false,
        });
      },

      openRegisterModal: () => {
        set({
          showRegisterModal: true,
          showLoginModal: false,
        });
      },

      closeRegisterModal: () => {
        set({
          showRegisterModal: false,
        });
      },

      updateUser: async (userData: Partial<User>) => {
        const currentUser = get().user;
        if (!currentUser) return;
        try {
          const data: any = await apiRequest('/api/auth/me', {
            method: 'PATCH',
            body: JSON.stringify({
              nickname: userData.nickname,
              bio: userData.bio,
              avatar: userData.avatar,
            }),
          });
          const user = normalizeUser(data);
          set({ user, isLoggedIn: true });
        } catch (error) {
          console.error('更新资料失败:', error);
          // 乐观更新
          set({
            user: normalizeUser({ ...currentUser, ...userData }),
          });
        }
      },

      refreshMe: async () => {
        const token = get().token;

        if (!token) {
          set({
            user: null,
            isLoggedIn: false,
          });
          return;
        }

        try {
          const data: any = await apiRequest('/api/auth/me');
          const user = normalizeUser(data);

          set({
            user,
            isLoggedIn: true,
          });
        } catch (error) {
          console.error('刷新用户信息失败:', error);

          set({
            token: null,
            user: null,
            isLoggedIn: false,
          });
        }
      },

        upgradeToCreator: async () => {
        try {
          const data: any = await apiRequest('/api/auth/upgrade-to-creator', {
            method: 'POST',
          });
          
          // 更新本地用户信息
          const currentUser = get().user;
          if (currentUser) {
            const updatedUser = {
              ...currentUser,
              userType: data.data?.userType ?? 1,
            };
            set({ user: updatedUser });
          }
          
          return true;
        } catch (error: any) {
          console.error('升级失败:', error);
          const message = error.message || '升级失败';
          alert(message);
          return false;
        }
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        token: state.token,
        user: state.user,
        isLoggedIn: state.isLoggedIn,
      }),
    }
  )
);