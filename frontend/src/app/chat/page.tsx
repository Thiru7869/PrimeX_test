"use client";

import { useEffect } from "react";
import { useChatStore } from "@/stores/chatStore";
import { useAuthStore } from "@/stores/authStore";
import ChatSidebar from "@/components/ChatSidebar";
import ChatWindow from "@/components/ChatWindow";
import MessageInput from "@/components/MessageInput";

export default function ChatPage() {
  const { isAuthenticated } = useAuthStore();
  const { loadChats } = useChatStore();

  useEffect(() => {
    if (isAuthenticated) loadChats();
  }, [isAuthenticated, loadChats]);

  return (
    <div className="flex h-screen">
      <ChatSidebar />
      <div className="flex flex-1 flex-col">
        <ChatWindow />
        <MessageInput />
      </div>
    </div>
  );
}