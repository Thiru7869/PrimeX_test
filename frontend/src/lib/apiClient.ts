import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

export const apiClient = axios.create({
  baseURL: API_URL,
  withCredentials: true,
  timeout: 20000,
});

let accessToken: string | null = null;

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken() {
  return accessToken;
}

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

let refreshPromise: Promise<string> | null = null;

async function doRefresh(): Promise<string> {
  const res = await axios.post(
    `${API_URL}/api/v1/auth/refresh`,
    {},
    {
      withCredentials: true,
      timeout: 20000,
    }
  );

  const newToken = res.data.access_token as string;
  setAccessToken(newToken);
  return newToken;
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & {
      _retried?: boolean;
    };

    const isAuthRoute =
      original?.url?.includes("/auth/refresh") ||
      original?.url?.includes("/auth/login");

    if (
      error.response?.status === 401 &&
      !original._retried &&
      !isAuthRoute
    ) {
      original._retried = true;

      try {
        if (!refreshPromise) {
          refreshPromise = doRefresh().finally(() => {
            refreshPromise = null;
          });
        }

        const newToken = await refreshPromise;

        original.headers.Authorization = `Bearer ${newToken}`;

        return apiClient(original);
      } catch (refreshError) {
        setAccessToken(null);
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);