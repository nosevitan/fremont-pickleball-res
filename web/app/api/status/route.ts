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

async function fetchVariable(token: string, name: string): Promise<string | null> {
  try {
    const res = await fetch(
      `https://api.github.com/repos/${REPO}/actions/variables/${name}`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/vnd.github+json",
          "X-GitHub-Api-Version": "2022-11-28",
        },
        cache: "no-store",
      }
    );
    if (!res.ok) return null;
    const data = await res.json();
    return data.value || null;
  } catch {
    return null;
  }
}

export async function GET() {
  const token = process.env.GITHUB_TOKEN;
  if (!token) {
    return NextResponse.json(
      { error: "GITHUB_TOKEN not configured" },
      { status: 500 }
    );
  }

  const [enabledVal, lastResultVal] = await Promise.all([
    fetchVariable(token, "BOOKING_ENABLED"),
    fetchVariable(token, "LAST_BOOKING_RESULT"),
  ]);

  const enabled = enabledVal === "true";
  let lastBooking = null;

  if (lastResultVal) {
    try {
      lastBooking = JSON.parse(lastResultVal);
    } catch {
      lastBooking = null;
    }
  }

  return NextResponse.json({
    enabled,
    nextBookingDate: getNextBookingDate(),
    lastBooking,
  });
}
