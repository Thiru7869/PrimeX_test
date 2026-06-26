import { apiClient } from "@/lib/apiClient";
import type { ChatSummary, ChatDetail, Message } from "@/lib/types";

export async function listChatsApi(): Promise<ChatSummary[]> {
  const res = await apiClient.get<ChatSummary[]>("/api/v1/chats");
  return res.data;
}

export async function createChatApi(title?: string): Promise<ChatSummary> {
  const res = await apiClient.post<ChatSummary>(
    "/api/v1/chats",
    {
      title: title || null,
    },
    {
      timeout: 45000, // Allow extra time for Render cold starts
    }
  );

  return res.data;
}

export async function getChatApi(chatId: string): Promise<ChatDetail> {
  const res = await apiClient.get<ChatDetail>(`/api/v1/chats/${chatId}`);
  return res.data;
}

export async function sendMessageApi(
  chatId: string,
  content: string
): Promise<Message> {
  const res = await apiClient.post<Message>(
    `/api/v1/chats/${chatId}/messages`,
    {
      content,
    },
    {
      timeout: 60000, // Allow AI response + provider fallback
    }
  );

  return res.data;
}