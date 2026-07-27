export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

export type ChatState = {
  messages: ChatMessage[];
  loading: boolean;
  error: string | null;
};