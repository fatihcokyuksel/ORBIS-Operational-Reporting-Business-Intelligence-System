import { NextResponse } from "next/server";
import { fetchBackend, getBackendApiCandidates } from "@/lib/backend-api";

function copyRequestHeaders(req: Request): Headers {
  const headers = new Headers();
  const contentType = req.headers.get("content-type");
  const accept = req.headers.get("accept");
  const cookie = req.headers.get("cookie");
  const authorization = req.headers.get("authorization");

  if (contentType) headers.set("content-type", contentType);
  if (accept) headers.set("accept", accept);
  if (cookie) headers.set("cookie", cookie);
  if (authorization) headers.set("authorization", authorization);

  return headers;
}

function copyResponseHeaders(upstream: Response): Headers {
  const headers = new Headers();
  const contentType = upstream.headers.get("content-type");
  const setCookie = upstream.headers.get("set-cookie");
  const contentDisposition = upstream.headers.get("content-disposition");

  if (contentType) headers.set("content-type", contentType);
  if (setCookie) headers.set("set-cookie", setCookie);
  if (contentDisposition) headers.set("content-disposition", contentDisposition);

  return headers;
}

export async function proxyToBackend(req: Request, pathname: string) {
  const incomingUrl = new URL(req.url);
  const method = req.method.toUpperCase();
  const hasBody = method !== "GET" && method !== "HEAD";

  let upstream: Response;
  try {
    upstream = await fetchBackend(`${pathname}${incomingUrl.search}`, {
      method,
      headers: copyRequestHeaders(req),
      body: hasBody ? await req.arrayBuffer() : undefined,
      cache: "no-store",
    });
  } catch (error) {
    console.error(`Backend API proxy failed for ${method} ${pathname}`, error);
    return NextResponse.json(
      {
        message: `Chatbot API'ye ulaşılamadı. Lütfen FastAPI backend'ini şu adreslerden birinde çalıştırın: ${getBackendApiCandidates().join(", ")}`,
      },
      { status: 503 },
    );
  }

  return new NextResponse(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: copyResponseHeaders(upstream),
  });
}
