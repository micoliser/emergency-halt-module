const ALLOWED = new Set(["all"]);

function isProtocolsPath(parts: string[]): boolean {
  return parts.length === 2 && parts[0] === "protocols" && /^\d+$/.test(parts[1]);
}

function backendBase(): string {
  const raw =
    process.env.API_URL?.trim() ||
    process.env.NEXT_PUBLIC_API_URL?.trim() ||
    "http://localhost:8000";
  return raw.replace(/\/$/, "");
}

async function proxySync(backendPath: string): Promise<Response> {
  const headers: Record<string, string> = {
    Accept: "application/json",
  };
  const secret = process.env.SYNC_SHARED_SECRET?.trim();
  if (secret) {
    headers["X-Sync-Secret"] = secret;
  }

  const target = `${backendBase()}${backendPath}`;
  let upstream: Response;
  try {
    upstream = await fetch(target, {
      method: "POST",
      headers,
      cache: "no-store",
    });
  } catch (err) {
    const detail = err instanceof Error ? err.message : "Could not reach the indexer.";
    return Response.json({ detail }, { status: 502 });
  }

  const text = await upstream.text();
  return new Response(text, {
    status: upstream.status,
    headers: {
      "Content-Type": upstream.headers.get("Content-Type") || "application/json",
    },
  });
}

export async function POST(
  _request: Request,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  const parts = (path ?? []).filter(Boolean);

  if (parts.length === 1 && ALLOWED.has(parts[0])) {
    return proxySync("/api/sync/all/");
  }
  if (isProtocolsPath(parts)) {
    return proxySync(`/api/sync/protocols/${parts[1]}/`);
  }

  return Response.json(
    { detail: "Unknown sync route. Use /api/sync/all or /api/sync/protocols/{id}." },
    { status: 404 },
  );
}
