import { ChatInterface } from "@/components/chat/ChatInterface";

export default function Home() {
  return (
    <div className="flex flex-col flex-1 h-full max-h-full">
      <ChatInterface />
    </div>
  );
}
