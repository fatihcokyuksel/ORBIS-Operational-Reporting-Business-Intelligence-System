import { Suspense } from "react";
import { ChatInterface } from "@/components/chat/ChatInterface";

export default function Home() {
  return (
    <div className="flex flex-col flex-1 h-full">
      <Suspense>
        <ChatInterface />
      </Suspense>
    </div>
  );
}
