import { NextResponse } from "next/server";

const BASE = "https://anc.apm.activecommunities.com/fremont";
const USERNAME = process.env.ACTIVENET_USERNAME || "";
const PASSWORD = process.env.ACTIVENET_PASSWORD || "";

interface ScheduleItem {
  schedule_date: string;
  time_text: string;
  activity_name: string;
  facilities: { facility_id: number; facility_name: string }[];
  centers: { id: number; name: string }[];
}

export async function GET() {
  if (!USERNAME || !PASSWORD) {
    return NextResponse.json({ bookings: [], error: "Credentials not configured" });
  }

  try {
    // Step 1: Get the signin page to establish cookies
    const signinRes = await fetch(`${BASE}/signin`, {
      redirect: "manual",
      headers: { "User-Agent": "Mozilla/5.0" },
    });
    const signinCookies = signinRes.headers.getSetCookie?.() || [];

    // Step 2: Try to login via the REST API
    // First, get the login page to capture any session cookie
    let allCookies = signinCookies.map((c) => c.split(";")[0]).join("; ");

    // POST login credentials
    const loginRes = await fetch(`${BASE}/rest/login?locale=en-US`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Cookie: allCookies,
        "User-Agent": "Mozilla/5.0",
      },
      body: JSON.stringify({
        login_name: USERNAME,
        login_password: PASSWORD,
      }),
      redirect: "manual",
    });

    // Collect login cookies
    const loginCookies = loginRes.headers.getSetCookie?.() || [];
    const cookieMap = new Map<string, string>();
    [...signinCookies, ...loginCookies].forEach((c) => {
      const [kv] = c.split(";");
      const [k, v] = kv.split("=");
      if (k && v) cookieMap.set(k.trim(), v.trim());
    });
    allCookies = Array.from(cookieMap.entries()).map(([k, v]) => `${k}=${v}`).join("; ");

    // Step 3: Fetch family schedules
    const today = new Date();
    const startDate = today.toISOString().split("T")[0];
    const endDate = new Date(today.getTime() + 30 * 86400000).toISOString().split("T")[0];

    const schedRes = await fetch(
      `${BASE}/rest/myaccount/familyschedules?start_date=${startDate}&end_date=${endDate}&locale=en-US`,
      {
        headers: {
          Cookie: allCookies,
          "User-Agent": "Mozilla/5.0",
          Accept: "application/json",
        },
      }
    );

    const schedData = await schedRes.json();
    const schedules: ScheduleItem[] = schedData?.body?.schedules || [];

    const bookings = schedules.map((s) => ({
      date: s.schedule_date,
      time: s.time_text,
      court: s.facilities?.[0]?.facility_name || "",
      center: s.centers?.[0]?.name || "",
      event: s.activity_name || "",
    }));

    // Sort by date
    bookings.sort((a, b) => a.date.localeCompare(b.date));

    // Only future
    const todayStr = startDate;
    const futureBookings = bookings.filter((b) => b.date >= todayStr);

    // If we got bookings, return them
    if (futureBookings.length > 0) {
      return NextResponse.json({ bookings: futureBookings });
    }

    // If empty, fall through to cached data
    throw new Error("No bookings from live API, trying cache");
  } catch (error) {
    console.error("Failed to fetch bookings:", error);

    // Fallback: try reading cached data from GitHub variable
    const token = process.env.GITHUB_TOKEN;
    if (token) {
      try {
        const ghRes = await fetch(
          "https://api.github.com/repos/nosevitan/fremont-pickleball-res/actions/variables/UPCOMING_BOOKINGS",
          {
            headers: {
              Authorization: `Bearer ${token}`,
              Accept: "application/vnd.github+json",
            },
            cache: "no-store",
          }
        );
        if (ghRes.ok) {
          const ghData = await ghRes.json();
          return NextResponse.json({
            bookings: JSON.parse(ghData.value || "[]"),
            cached: true,
          });
        }
      } catch {}
    }

    return NextResponse.json({ bookings: [] });
  }
}
