declare const __STREAMHUB_API_BASE_URL__: string;

const API_BASE = (
  __STREAMHUB_API_BASE_URL__ ||
  'http://127.0.0.1:8000'
).replace(/\/$/, '');

function getToken(): string | null {
  try {
    const raw = localStorage.getItem('auth-storage');

    if (!raw) return null;

    const parsed = JSON.parse(raw);

    return parsed?.state?.token || null;
  } catch {
    return null;
  }
}

function isAbsoluteUrl(url: string) {
  return /^https?:\/\//i.test(url);
}

async function parseResponseBody(response: Response) {
  const text = await response.text();

  if (!text) return null;

  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export class ApiError extends Error {
  status: number;
  data?: unknown;

  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

export async function apiRequest<T = any>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();

  const isFormData =
    typeof FormData !== 'undefined' && options.body instanceof FormData;

  const headers: Record<string, string> = {
    ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
    ...((options.headers as Record<string, string>) || {}),
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const url = isAbsoluteUrl(path) ? path : `${API_BASE}${path}`;

  let response: Response;

  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (error) {
    console.error('网络请求失败:', error);
    throw new ApiError(
      '无法连接后端服务，请确认 FastAPI 后端已经启动：http://127.0.0.1:8000',
      0,
      error
    );
  }

  const data = await parseResponseBody(response);

  if (!response.ok) {
    let message = `请求失败：${response.status}`;

    if (typeof data === 'string') {
      message = data || message;
    } else if (data && typeof data === 'object') {
      const anyData = data as any;
      message =
        anyData.detail ||
        anyData.error ||
        anyData.message ||
        message;
    }

    throw new ApiError(message, response.status, data);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return data as T;
}

export { API_BASE };

export const changePassword = async (oldPassword: string, newPassword: string) => {
  return apiRequest('/api/auth/change-password', {
    method: 'PUT',
    body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
  });
};

// 获取创作者统计数据（粉丝数）
export const getCreatorFans = async () => {
  const data: any = await apiRequest('/api/creator/fans?page=1&limit=100');
  return data;
};

// 获取创作者收到的评论
export const getCreatorComments = async () => {
  const data: any = await apiRequest('/api/creator/comments?page=1&limit=100');
  return data;
};