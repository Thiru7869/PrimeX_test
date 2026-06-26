"use client";

import { useEffect, useRef } from "react";
import { useChatStore } from "@/stores/chatStore";

export default function ChatWindow() {
  const { messages, isSending, activeChatId } = useChatStore();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isSending]);

  if (!activeChatId) {
    return (
      <div className="flex flex-1 items-center justify-center text-gray-400">
        Select a chat or create a new one to begin.
      </div>
    );
  }

  return (
    <div className="flex-1 space-y-4 overflow-y-auto bg-white p-6">
      {messages.map((m) => (
        <div
          key={m.id}
          className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
        >
          <div
            className={`max-w-[75%] whitespace-pre-wrap rounded-2xl px-4 py-2 text-sm ${
              m.role === "user" ? "bg-black text-white" : "bg-gray-100 text-gray-900"
            }`}
          >
            {m.content}
          </div>
        </div>
      ))}
      {isSending && (
        <div className="flex justify-start">
          <div className="rounded-2xl bg-gray-100 px-4 py-2 text-sm text-gray-500">
            Thinking…
          </div>
        </div>
      )}
      <div ref={bottomRef} />
    </div>
  );
}