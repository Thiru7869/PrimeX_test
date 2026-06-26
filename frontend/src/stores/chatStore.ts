import { create } from "zustand";
import type { ChatSummary, Message } from "@/lib/types";
import {
  listChatsApi,
  createChatApi,
  getChatApi,
  sendMessageApi,
} from "@/services/chatApi";

interface ChatState {
  chats: ChatSummary[];
  activeChatId: string | null;
  messages: Message[];
  isSending: boolean;
  loadChats: () => Promise<void>;
  createChat: () => Promise<void>;
  selectChat: (chatId: string) => Promise<void>;
  sendMessage: (content: string) => Promise<void>;
  reset: () => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  chats: [],
  activeChatId: null,
  messages: [],
  isSending: false,

  loadChats: async () => {
    const chats = await listChatsApi();
    set({ chats });
  },

  createChat: async () => {
    const chat = await createChatApi();
    set((s) => ({ chats: [chat, ...s.chats], activeChatId: chat.id, messages: [] }));
  },

  selectChat: async (chatId) => {
    set({ activeChatId: chatId, messages: [] });
    const detail = await getChatApi(chatId);
    set({ messages: detail.messages });
  },

  sendMessage: async (content) => {
    const chatId = get().activeChatId;
    if (!chatId) return;

    // Optimistically show the user's message immediately.
    const tempUserMsg: Message = {
      id: `temp-${Date.now()}`,
      role: "user",
      content,
      created_at: new Date().toISOString(),
    };
    set((s) => ({ messages: [...s.messages, tempUserMsg], isSending: true }));

    try {
      const assistantMsg = await sendMessageApi(chatId, content);
      set((s) => ({ messages: [...s.messages, assistantMsg], isSending: false }));
    } catch (err) {
      // Remove the optimistic message on failure.
      set((s) => ({
        messages: s.messages.filter((m) => m.id !== tempUserMsg.id),
        isSending: false,
      }));
      throw err;
    }
  },

  reset: () => set({ chats: [], activeChatId: null, messages: [], isSending: false }),
}));