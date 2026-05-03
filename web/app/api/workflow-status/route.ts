import { NextResponse } from "next/server";

const REPO = "nosevitan/fremont-pickleball-res";

export async function GET() {
  const token = process.env.GITHUB_TOKEN;
  if (!token) {
    return NextResponse.json({ error: "No token" }, { status: 500 });
  }

  try {
    // Get the most recent workflow run for book.yml
    const res = await fetch(
      `https://api.github.com/repos/${REPO}/actions/workflows/book.yml/runs?per_page=1`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/vnd.github+json",
        },
        cache: "no-store",
      }
    );

    if (!res.ok) {
      return NextResponse.json({ status: "unknown" });
    }

    const data = await res.json();
    const run = data.workflow_runs?.[0];

    if (!run) {
      return NextResponse.json({ status: "no_runs" });
    }

    // Also check the booking result variable
    let lastBooking = null;
    try {
      const varRes = await fetch(
        `https://api.github.com/repos/${REPO}/actions/variables/LAST_BOOKING_RESULT`,
        {
          headers: {
            Authorization: `Bearer ${token}`,
            Accept: "application/vnd.github+json",
          },
          cache: "no-store",
        }
      );
      if (varRes.ok) {
        const varData = await varRes.json();
        lastBooking = JSON.parse(varData.value || "null");
      }
    } catch {}

    return NextResponse.json({
      status: run.status,
      conclusion: run.conclusion,
      started: run.created_at,
      updated: run.updated_at,
      url: run.html_url,
      lastBooking,
    });
  } catch {
    return NextResponse.json({ status: "error" });
  }
}
