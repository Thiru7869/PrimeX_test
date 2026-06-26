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
  isCreating: boolean;
  error: string | null;

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
  isCreating: false,
  error: null,

  loadChats: async () => {
    const chats = await listChatsApi();
    set({ chats });
  },

  createChat: async () => {
    if (get().isCreating) return;

    set({
      isCreating: true,
      error: null,
    });

    try {
      const chat = await createChatApi();

      set((state) => ({
        chats: [chat, ...state.chats],
        activeChatId: chat.id,
        messages: [],
        isCreating: false,
      }));
    } catch {
      set({
        isCreating: false,
        error:
          "Couldn't create chat. The server may be waking up. Please try again.",
      });
    }
  },

  selectChat: async (chatId) => {
    set({
      activeChatId: chatId,
      messages: [],
    });

    const detail = await getChatApi(chatId);

    set({
      messages: detail.messages,
    });
  },

  sendMessage: async (content) => {
    const chatId = get().activeChatId;
    if (!chatId) return;

    const tempUserMsg: Message = {
      id: `temp-${Date.now()}`,
      role: "user",
      content,
      created_at: new Date().toISOString(),
    };

    set((state) => ({
      messages: [...state.messages, tempUserMsg],
      isSending: true,
    }));

    try {
      const assistantMsg = await sendMessageApi(chatId, content);

      set((state) => ({
        messages: [...state.messages, assistantMsg],
        isSending: false,
      }));
    } catch (err) {
      set((state) => ({
        messages: state.messages.filter((m) => m.id !== tempUserMsg.id),
        isSending: false,
      }));

      throw err;
    }
  },

  reset: () =>
    set({
      chats: [],
      activeChatId: null,
      messages: [],
      isSending: false,
      isCreating: false,
      error: null,
    }),
}));