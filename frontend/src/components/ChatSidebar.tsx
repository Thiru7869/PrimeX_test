"use client";

import { useChatStore } from "@/stores/chatStore";
import { useAuthStore } from "@/stores/authStore";
import { useRouter } from "next/navigation";

export default function ChatSidebar() {
  const { chats, activeChatId, createChat, selectChat } = useChatStore();
  const { user, logout } = useAuthStore();
  const router = useRouter();

  async function handleLogout() {
    await logout();
    router.replace("/login");
  }

  return (
    <aside className="flex h-screen w-64 flex-col border-r bg-gray-50">
      <div className="p-3">
        <button
          onClick={createChat}
          className="w-full rounded-lg bg-black py-2 text-sm text-white"
        >
          + New chat
        </button>
      </div>
      <div className="flex-1 overflow-y-auto px-2">
        {chats.map((chat) => (
          <button
            key={chat.id}
            onClick={() => selectChat(chat.id)}
            className={`mb-1 w-full truncate rounded-lg px-3 py-2 text-left text-sm ${
              chat.id === activeChatId ? "bg-gray-200" : "hover:bg-gray-100"
            }`}
          >
            {chat.title}
          </button>
        ))}
        {chats.length === 0 && (
          <p className="px-3 py-2 text-sm text-gray-400">No chats yet.</p>
        )}
      </div>
      <div className="border-t p-3 text-sm">
        <p className="mb-2 truncate text-gray-600">{user?.email}</p>
        <button
          onClick={handleLogout}
          className="w-full rounded-lg border py-2 text-gray-700 hover:bg-gray-100"
        >
          Log out
        </button>
      </div>
    </aside>
  );
}