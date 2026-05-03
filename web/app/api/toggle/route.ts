import { NextResponse } from "next/server";

const REPO = "nosevitan/fremont-pickleball-res";

export async function POST(request: Request) {
  const token = process.env.GITHUB_TOKEN;
  if (!token) {
    return NextResponse.json(
      { error: "GITHUB_TOKEN not configured" },
      { status: 500 }
    );
  }

  try {
    const body = await request.json();
    const newValue = body.enabled ? "true" : "false";

    const res = await fetch(
      `https://api.github.com/repos/${REPO}/actions/variables/BOOKING_ENABLED`,
      {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: "application/vnd.github+json",
          "X-GitHub-Api-Version": "2022-11-28",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          name: "BOOKING_ENABLED",
          value: newValue,
        }),
      }
    );

    if (!res.ok) {
      const text = await res.text();
      console.error("GitHub API error:", res.status, text);
      return NextResponse.json(
        { error: "Failed to update variable" },
        { status: 500 }
      );
    }

    return NextResponse.json({ enabled: body.enabled });
  } catch (error) {
    console.error("Failed to toggle:", error);
    return NextResponse.json(
      { error: "Failed to toggle" },
      { status: 500 }
    );
  }
}
