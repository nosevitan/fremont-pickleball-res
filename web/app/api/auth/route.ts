import { NextRequest, NextResponse } from "next/server";

const SITE_PASSWORD = process.env.SITE_PASSWORD || "Genesis1219@PI!";

export async function POST(req: NextRequest) {
  const { password } = await req.json();

  if (password === SITE_PASSWORD) {
    const res = NextResponse.json({ ok: true });
    res.cookies.set("pb_auth", "1", {
      httpOnly: true,
      secure: true,
      sameSite: "strict",
      maxAge: 60 * 60 * 24 * 30, // 30 days
      path: "/",
    });
    return res;
  }

  return NextResponse.json({ ok: false }, { status: 401 });
}
