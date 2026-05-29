import { apiRequest } from '../api';

export interface UserBrief {
  id: string;
  account: string;
  nickname: string;
  avatar: string;
  bio: string;
}

export interface FollowListItem extends UserBrief {
  isMutual?: boolean;
  followedAt?: string;
}

export interface Relation {
  isFollowing: boolean;
  isFollowedBy: boolean;
  isMutual: boolean;
  followerCount: number;
  followingCount: number;
}

export function getUserProfile(userId: string) {
  return apiRequest(`/api/users/${userId}`);
}

export function getRelation(userId: string) {
  return apiRequest<Relation>(`/api/users/${userId}/relation`);
}

export function followUser(userId: string) {
  return apiRequest<{ ok: boolean; isFollowing: boolean }>(
    `/api/users/${userId}/follow`,
    { method: 'POST' }
  );
}

export function unfollowUser(userId: string) {
  return apiRequest<{ ok: boolean; isFollowing: boolean }>(
    `/api/users/${userId}/follow`,
    { method: 'DELETE' }
  );
}

export function listFollowers(userId: string, offset = 0, limit = 20) {
  return apiRequest<FollowListItem[]>(
    `/api/users/${userId}/followers?offset=${offset}&limit=${limit}`
  );
}

export function listFollowing(userId: string, offset = 0, limit = 20) {
  return apiRequest<FollowListItem[]>(
    `/api/users/${userId}/following?offset=${offset}&limit=${limit}`
  );
}
