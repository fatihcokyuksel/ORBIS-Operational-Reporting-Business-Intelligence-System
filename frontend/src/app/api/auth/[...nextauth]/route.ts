import { NextResponse } from "next/server";

export async function GET() {
  return NextResponse.json({ message: "Bulunamadı" }, { status: 404 });
}

export async function POST() {
  return NextResponse.json({ message: "Bulunamadı" }, { status: 404 });
}
