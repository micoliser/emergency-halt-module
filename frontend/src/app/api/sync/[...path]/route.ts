const ALLOWED = new Set(["all"]);

/** Browser clients must send this so classic form CSRF cannot trigger sync. */
const CSRF_HEADER = "x-requested-with";
const CSRF_VALUE = "ProofHalt";

/** Simple in-memory rate limit for the sync proxy (per client IP). */
const RATE_LIMIT_WINDOW_MS = 60_000;
const RATE_LIMIT_MAX = 30;
const rateBuckets = new Map<string, { count: number; resetAt: number }>();

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

function clientIp(request: Request): string {
  const forwarded = request.headers.get("x-forwarded-for");
  if (forwarded) return forwarded.split(",")[0]?.trim() || "unknown";
  return request.headers.get("x-real-ip") || "unknown";
}

function rateLimitOk(ip: string): boolean {
  const now = Date.now();
  const bucket = rateBuckets.get(ip);
  if (!bucket || now >= bucket.resetAt) {
    rateBuckets.set(ip, { count: 1, resetAt: now + RATE_LIMIT_WINDOW_MS });
    return true;
  }
  if (bucket.count >= RATE_LIMIT_MAX) return false;
  bucket.count += 1;
  return true;
}

async function proxySync(backendPath: string): Promise<Response> {
  const headers: Record<string, string> = {
    Accept: "application/json",
  };
  const secret = process.env.SYNC_SHARED_SECRET?.trim();
  const isProd = process.env.NODE_ENV === "production";

  if (!secret) {
    if (isProd) {
      return Response.json(
        {
          detail:
            "SYNC_SHARED_SECRET is not configured. Refusing to proxy sync in production.",
        },
        { status: 503 },
      );
    }
    // Local DEBUG-style: backend may also allow empty secret when DEBUG=True.
  } else {
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
  request: Request,
  context: { params: Promise<{ path: string[] }> },
) {
  const requestedWith = request.headers.get(CSRF_HEADER);
  if (requestedWith !== CSRF_VALUE) {
    return Response.json(
      { detail: `Missing or invalid ${CSRF_HEADER} header.` },
      { status: 403 },
    );
  }

  if (!rateLimitOk(clientIp(request))) {
    return Response.json(
      { detail: "Too many sync requests. Try again shortly." },
      { status: 429 },
    );
  }

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
