import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { SESSION_COOKIE } from "@/lib/auth";
import { resolveMarketingFile } from "@/lib/marketing";

const PUBLIC_PATHS = ["/login", "/", "/home", "/about", "/services", "/projects", "/contact", "/api/contact"];

const PUBLIC_PREFIXES = ["/css/", "/js/", "/lib/", "/img/", "/home/"];

function isPublicAsset(pathname: string): boolean {
  return PUBLIC_PREFIXES.some((prefix) => pathname.startsWith(prefix));
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasSession = Boolean(request.cookies.get(SESSION_COOKIE)?.value);

  if (isPublicAsset(pathname)) {
    return NextResponse.next();
  }

  const marketingFile = resolveMarketingFile(pathname);
  if (marketingFile) {
    const url = request.nextUrl.clone();
    url.pathname = marketingFile;
    return NextResponse.rewrite(url);
  }

  const isPublic = PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`));

  if (!isPublic && !hasSession) {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.searchParams.set("next", pathname);
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
