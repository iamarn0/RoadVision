import { NextResponse } from "next/server";
import { validateContact } from "@/lib/contact";

const WINDOW_MS = 10 * 60 * 1000;
const MAX_REQUESTS = 8;
const hits = new Map<string, number[]>();

function clientKey(request: Request): string {
  const forwarded = request.headers.get("x-forwarded-for");
  return forwarded?.split(",")[0]?.trim() || "local";
}

function tooMany(key: string): boolean {
  const now = Date.now();
  const recent = (hits.get(key) ?? []).filter((stamp) => now - stamp < WINDOW_MS);
  recent.push(now);
  hits.set(key, recent);
  return recent.length > MAX_REQUESTS;
}

export async function POST(request: Request) {
  if (tooMany(clientKey(request))) {
    return NextResponse.json(
      { ok: false, message: "Too many messages. Please wait a few minutes and try again." },
      { status: 429 },
    );
  }

  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json({ ok: false, message: "Please send a valid enquiry." }, { status: 400 });
  }

  const result = validateContact(payload);
  if (!result.ok) {
    return NextResponse.json({ ok: false, message: result.message }, { status: 400 });
  }

  console.info("[contact]", result.data.type, result.data.email, result.data.service);
  return NextResponse.json({
    ok: true,
    message:
      result.data.type === "newsletter"
        ? "Thanks. We will send RoadVision updates to this email."
        : "Thanks. Our team will get back to you within one business day.",
  });
}
