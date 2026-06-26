import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

// The Axios instance every API call uses.
// withCredentials: true → the browser sends/receives the HttpOnly refresh cookie.
export const apiClient = axios.create({
  baseURL: API_URL,
  withCredentials: true,
});

// --- Access token kept in memory (NOT localStorage) ---
// The auth store calls setAccessToken() whenever it changes.
let accessToken: string | null = null;
export function setAccessToken(token: string | null) {
  accessToken = token;
}
export function getAccessToken() {
  return accessToken;
}

// --- Request interceptor: attach the token to every call ---
apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`;
  }
  return config;
});

// --- Response interceptor: on 401, refresh once, then retry the original call ---
//
// "Single-flight": if 5 calls 401 at the same time, we must refresh only ONCE,
// not 5 times (5 refreshes would fight each other and rotate the cookie wrongly).
// We do this by sharing ONE refresh promise across all waiting calls.
let refreshPromise: Promise<string> | null = null;

async function doRefresh(): Promise<string> {
  const res = await axios.post(
    `${API_URL}/api/v1/auth/refresh`,
    {},
    { withCredentials: true } // send the refresh cookie
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

    // Only handle 401s, only retry once, and never try to refresh the refresh call itself.
    const isAuthRoute = original?.url?.includes("/auth/refresh") || original?.url?.includes("/auth/login");
    if (error.response?.status === 401 && !original._retried && !isAuthRoute) {
      original._retried = true;
      try {
        // Share one refresh across all concurrent 401s.
        if (!refreshPromise) {
          refreshPromise = doRefresh().finally(() => {
            refreshPromise = null;
          });
        }
        const newToken = await refreshPromise;
        original.headers.Authorization = `Bearer ${newToken}`;
        return apiClient(original); // retry the original request
      } catch (refreshError) {
        // Refresh failed → session is truly dead. Let the caller handle logout.
        setAccessToken(null);
        return Promise.reject(refreshError);
      }
    }
    return Promise.reject(error);
  }
);