import { NextRequest, NextResponse } from "next/server";

export function middleware(req: NextRequest) {
  // Allow the auth endpoint through
  if (req.nextUrl.pathname === "/api/auth") {
    return NextResponse.next();
  }

  // Check for auth cookie
  const auth = req.cookies.get("pb_auth");
  if (auth?.value === "1") {
    return NextResponse.next();
  }

  // For API routes, return 401
  if (req.nextUrl.pathname.startsWith("/api/")) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  // For page routes, let through (the page itself handles showing login)
  return NextResponse.next();
}

export const config = {
  matcher: ["/api/:path*"],
};
