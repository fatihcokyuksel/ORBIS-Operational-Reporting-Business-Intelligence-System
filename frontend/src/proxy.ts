import { NextRequest, NextResponse } from "next/server";
import { fetchBackend } from "@/lib/backend-api";

const publicRoutes = ["/login", "/signin", "/signup", "/api/auth/login", "/api/auth/register"];
const protectedRoutes = ["/", "/chat", "/reports"];

async function hasActiveSession(req: NextRequest, cookie: string) {
  if (!cookie) {
    return false;
  }

  try {
    const res = await fetchBackend("/api/auth/session", {
      headers: {
        cookie: req.headers.get("cookie") ?? "",
        accept: "application/json",
      },
    });

    if (!res.ok) {
      return false;
    }

    const data = (await res.json()) as { user?: unknown };
    return Boolean(data.user);
  } catch (error) {
    console.error("Proxy session validation failed", error);
    return false;
  }
}

function redirectToLogin(req: NextRequest) {
  const res = NextResponse.redirect(new URL("/login", req.nextUrl));
  res.cookies.delete("session");
  return res;
}

export default async function proxy(req: NextRequest) {
  const path = req.nextUrl.pathname;
  const isProtectedRoute = protectedRoutes.some((route) => path === route || path.startsWith("/chat/"));
  const isPublicRoute = publicRoutes.includes(path);
  const cookie = req.cookies.get("session")?.value;

  if (!cookie) {
    if (isProtectedRoute) {
      return NextResponse.redirect(new URL("/login", req.nextUrl));
    }
    return NextResponse.next();
  }

  const hasSession = await hasActiveSession(req, cookie);

  if (isProtectedRoute && !hasSession) {
    return redirectToLogin(req);
  }

  if (isPublicRoute && hasSession) {
    return NextResponse.redirect(new URL("/", req.nextUrl));
  }

  if (isPublicRoute && !hasSession) {
    const res = NextResponse.next();
    res.cookies.delete("session");
    return res;
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico).*)",
  ],
};
