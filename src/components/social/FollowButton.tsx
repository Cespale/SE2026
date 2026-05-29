import React, { useEffect, useState } from 'react';
import { followUser, unfollowUser, getRelation } from '../../api/social';
import { useAuthStore } from '../../stores/authStore';

interface Props {
  userId: string;
  size?: 'sm' | 'md';
  onChange?: (isFollowing: boolean) => void;
}

export function FollowButton({ userId, size = 'md', onChange }: Props) {
  const { user: me, isLoggedIn, openLoginModal } = useAuthStore();
  const [isFollowing, setIsFollowing] = useState(false);
  const [isMutual, setIsMutual] = useState(false);
  const [loading, setLoading] = useState(false);

  const isSelf = me?.id === userId;

  useEffect(() => {
    if (!isLoggedIn || isSelf || !userId) return;
    getRelation(userId)
      .then((r) => {
        setIsFollowing(r.isFollowing);
        setIsMutual(r.isMutual);
      })
      .catch(() => {});
  }, [userId, isLoggedIn, isSelf]);

  if (isSelf) return null;

  async function toggle() {
    if (!isLoggedIn) {
      openLoginModal();
      return;
    }
    if (loading) return;
    setLoading(true);
    try {
      if (isFollowing) {
        await unfollowUser(userId);
        setIsFollowing(false);
        setIsMutual(false);
        onChange?.(false);
      } else {
        await followUser(userId);
        setIsFollowing(true);
        onChange?.(true);
      }
    } catch (e: any) {
      alert(e?.message || '操作失败');
    } finally {
      setLoading(false);
    }
  }

  const padding = size === 'sm' ? 'px-3 py-1 text-sm' : 'px-6 py-2';
  const label = isFollowing
    ? isMutual
      ? '互相关注'
      : '已关注'
    : '关注';
  const className = isFollowing
    ? `${padding} bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-200 rounded-full hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors`
    : `${padding} bg-blue-500 text-white rounded-full hover:bg-blue-600 transition-colors`;

  return (
    <button onClick={toggle} disabled={loading} className={className}>
      {loading ? '...' : label}
    </button>
  );
}
