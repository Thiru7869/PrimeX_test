"use client";

import { useState } from "react";
import { useChatStore } from "@/stores/chatStore";

export default function MessageInput() {
  const { sendMessage, isSending, activeChatId } = useChatStore();
  const [text, setText] = useState("");

  async function handleSend() {
    const content = text.trim();
    if (!content || isSending) return;
    setText("");
    try {
      await sendMessage(content);
    } catch {
      // simplest error UX: restore the text so the user can retry
      setText(content);
    }
  }

  return (
    <div className="border-t bg-white p-3">
      <div className="flex gap-2">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          placeholder={activeChatId ? "Type a message…" : "Create or select a chat first"}
          disabled={!activeChatId || isSending}
          rows={1}
          className="flex-1 resize-none rounded-lg border px-3 py-2 disabled:bg-gray-100"
        />
        <button
          onClick={handleSend}
          disabled={!activeChatId || isSending || !text.trim()}
          className="rounded-lg bg-black px-4 text-white disabled:opacity-50"
        >
          {isSending ? "…" : "Send"}
        </button>
      </div>
    </div>
  );
}