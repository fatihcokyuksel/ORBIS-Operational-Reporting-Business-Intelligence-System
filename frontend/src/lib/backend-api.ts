const configuredBackendUrl =
  process.env.BACKEND_API_URL || process.env.NEXT_PUBLIC_API_URL;

function normalizeBaseUrl(url: string) {
  return url.endsWith("/") ? url.slice(0, -1) : url;
}

function createCandidateUrls() {
  const candidates = [
    configuredBackendUrl,
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://127.0.0.1:8001",
    "http://localhost:8001",
  ].filter(Boolean) as string[];

  return [...new Set(candidates.map(normalizeBaseUrl))];
}

export function getBackendApiCandidates() {
  return createCandidateUrls();
}

export async function fetchBackend(pathname: string, init?: RequestInit) {
  const errors: Error[] = [];

  for (const baseUrl of createCandidateUrls()) {
    try {
      return await fetch(new URL(pathname, `${baseUrl}/`), init);
    } catch (error) {
      errors.push(
        error instanceof Error
          ? error
          : new Error(`Unknown backend fetch error for ${baseUrl}`),
      );
    }
  }

  throw new AggregateError(
    errors,
    `Backend API is unreachable for ${pathname}`,
  );
}
