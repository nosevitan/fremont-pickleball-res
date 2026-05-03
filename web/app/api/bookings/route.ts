import { NextResponse } from "next/server";

const REPO = "nosevitan/fremont-pickleball-res";

export async function GET() {
  const token = process.env.GITHUB_TOKEN;
  if (!token) {
    return NextResponse.json({ error: "GITHUB_TOKEN not configured" }, { status: 500 });
  }

  // Trigger a GitHub Actions workflow that scrapes bookings and saves to a variable
  // For now, read the cached result from UPCOMING_BOOKINGS variable
  try {
    const res = await fetch(
      `https://api.github.com/repos/${REPO}/actions/variables/UPCOMING_BOOKINGS`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/vnd.github+json",
          "X-GitHub-Api-Version": "2022-11-28",
        },
        cache: "no-store",
      }
    );

    if (!res.ok) {
      return NextResponse.json({ bookings: [] });
    }

    const data = await res.json();
    const bookings = JSON.parse(data.value || "[]");
    return NextResponse.json({ bookings });
  } catch {
    return NextResponse.json({ bookings: [] });
  }
}
