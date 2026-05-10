import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/session";

const GREETING = "Merhaba! Ben FatihGPT. Finans ve Muhasebe hakkında bana her şeyi sorabilirsin! Sana nasıl yardımcı olabilirim?";

export async function GET() {
  try {
    const session = await getSession();
    if (!session) {
      return NextResponse.json({ message: "Unauthorized" }, { status: 401 });
    }

    const chats = await prisma.chatSession.findMany({
      where: { userId: session.userId as string },
      orderBy: { updatedAt: "desc" },
    });

    // Sort pinned first in JS to avoid driver adapter issues
    const sorted = chats.sort((a, b) => {
      if (a.isPinned !== b.isPinned) return a.isPinned ? -1 : 1;
      return 0; // preserve DB order (updatedAt desc) within each group
    });

    return NextResponse.json(sorted);
  } catch (error) {
    console.error("GET /api/chats error:", error);
    return NextResponse.json({ message: "Internal Server Error" }, { status: 500 });
  }
}

export async function POST(req: Request) {
  try {
    const session = await getSession();
    if (!session) {
      return NextResponse.json({ message: "Unauthorized" }, { status: 401 });
    }

    const { title } = await req.json();

    const chat = await prisma.chatSession.create({
      data: {
        title: title || "New Chat",
        userId: session.userId as string,
      },
    });

    // Auto-insert greeting message
    await prisma.message.create({
      data: {
        sessionId: chat.id,
        role: "assistant",
        content: GREETING,
      },
    });

    return NextResponse.json(chat);
  } catch (error) {
    return NextResponse.json({ message: "Internal Server Error" }, { status: 500 });
  }
}
