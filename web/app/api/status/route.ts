import { NextResponse } from "next/server";

const REPO = "nosevitan/fremont-pickleball-res";

function getNextBookingDate(): string {
  const date = new Date();
  date.setDate(date.getDate() + 7);
  return date.toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

export async function GET() {
  const token = process.env.GITHUB_TOKEN;
  if (!token) {
    return NextResponse.json(
      { error: "GITHUB_TOKEN not configured" },
      { status: 500 }
    );
  }

  try {
    const res = await fetch(
      `https://api.github.com/repos/${REPO}/actions/variables/BOOKING_ENABLED`,
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
      const text = await res.text();
      console.error("GitHub API error:", res.status, text);
      return NextResponse.json(
        { enabled: false, nextBookingDate: getNextBookingDate() }
      );
    }

    const data = await res.json();
    const enabled = data.value === "true";

    return NextResponse.json({
      enabled,
      nextBookingDate: getNextBookingDate(),
    });
  } catch (error) {
    console.error("Failed to fetch status:", error);
    return NextResponse.json(
      { enabled: false, nextBookingDate: getNextBookingDate() }
    );
  }
}
