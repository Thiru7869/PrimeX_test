export interface User {
  id: string;
  email: string;
  display_name: string | null;
  role: string;
  is_verified: boolean;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface ChatSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export interface ChatDetail {
  id: string;
  title: string;
  created_at: string;
  messages: Message[];
}