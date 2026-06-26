import axios from "axios";
import { apiClient, setAccessToken } from "@/lib/apiClient";
import type { AuthResponse, User } from "@/lib/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

export async function registerApi(
  email: string,
  password: string,
  displayName?: string
): Promise<AuthResponse> {
  const res = await apiClient.post<AuthResponse>("/api/v1/auth/register", {
    email,
    password,
    display_name: displayName || null,
  });
  return res.data;
}

export async function loginApi(
  email: string,
  password: string
): Promise<AuthResponse> {
  const res = await apiClient.post<AuthResponse>("/api/v1/auth/login", {
    email,
    password,
  });
  return res.data;
}

export async function logoutApi(): Promise<void> {
  await apiClient.post("/api/v1/auth/logout");
  setAccessToken(null);
}

// Called on app load to restore a session: uses the cookie to get a fresh token.
export async function restoreSessionApi(): Promise<string | null> {
  try {
    const res = await axios.post(
      `${API_URL}/api/v1/auth/refresh`,
      {},
      { withCredentials: true }
    );
    const token = res.data.access_token as string;
    setAccessToken(token);
    return token;
  } catch {
    return null; // no valid cookie → not logged in
  }
}

export async function getMeApi(): Promise<User> {
  const res = await apiClient.get<User>("/api/v1/auth/me");
  return res.data;
}