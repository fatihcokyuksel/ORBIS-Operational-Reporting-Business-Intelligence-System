import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/session";

export async function GET(req: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const session = await getSession();
    if (!session) return NextResponse.json({ message: "Unauthorized" }, { status: 401 });

    const id = (await params).id;

    const chat = await prisma.chatSession.findUnique({
      where: { id },
    });

    if (!chat || chat.userId !== session.userId) {
      return NextResponse.json({ message: "Not found" }, { status: 404 });
    }

    const messages = await prisma.message.findMany({
      where: { sessionId: id },
      orderBy: { createdAt: "asc" },
    });

    return NextResponse.json(messages);
  } catch (error) {
    return NextResponse.json({ message: "Internal Server Error" }, { status: 500 });
  }
}

export async function POST(req: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const session = await getSession();
    if (!session) return NextResponse.json({ message: "Unauthorized" }, { status: 401 });

    const id = (await params).id;
    const { role, content } = await req.json();

    const chat = await prisma.chatSession.findUnique({
      where: { id },
    });

    if (!chat || chat.userId !== session.userId) {
      return NextResponse.json({ message: "Not found" }, { status: 404 });
    }

    const message = await prisma.message.create({
      data: {
        sessionId: id,
        role,
        content,
      },
    });

    await prisma.chatSession.update({
      where: { id },
      data: { updatedAt: new Date() }
    });

    return NextResponse.json(message);
  } catch (error) {
    return NextResponse.json({ message: "Internal Server Error" }, { status: 500 });
  }
}
