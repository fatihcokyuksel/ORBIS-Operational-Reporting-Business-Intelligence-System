import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { getSession } from "@/lib/session";

export async function DELETE(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const session = await getSession();
    if (!session) return NextResponse.json({ message: "Unauthorized" }, { status: 401 });

    const id = (await params).id;

    const chat = await prisma.chatSession.findUnique({ where: { id } });
    if (!chat || chat.userId !== session.userId) {
      return NextResponse.json({ message: "Not found" }, { status: 404 });
    }

    // Cascade deletes messages due to schema relation
    await prisma.chatSession.delete({ where: { id } });

    return NextResponse.json({ success: true });
  } catch (error) {
    return NextResponse.json({ message: "Internal Server Error" }, { status: 500 });
  }
}

export async function PATCH(req: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const session = await getSession();
    if (!session) return NextResponse.json({ message: "Unauthorized" }, { status: 401 });

    const id = (await params).id;
    const body = await req.json();

    const chat = await prisma.chatSession.findUnique({ where: { id } });
    if (!chat || chat.userId !== session.userId) {
      return NextResponse.json({ message: "Not found" }, { status: 404 });
    }

    const updated = await prisma.chatSession.update({
      where: { id },
      data: {
        ...(typeof body.isPinned === "boolean" && { isPinned: body.isPinned }),
        ...(typeof body.title === "string" && { title: body.title }),
      },
    });

    return NextResponse.json(updated);
  } catch (error) {
    return NextResponse.json({ message: "Internal Server Error" }, { status: 500 });
  }
}
