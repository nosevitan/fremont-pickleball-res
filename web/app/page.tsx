"use client";

import { useState, useEffect, useCallback } from "react";

interface LastBooking {
  status: string;
  date: string;
  court: string;
  timestamp: string;
}

interface Booking {
  date: string;
  time: string;
  court: string;
  center: string;
  event: string;
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + "T12:00:00");
  return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
}

function formatCourt(court: string): string {
  return court.replace("FTC Pickleball ", "").replace("FTC ", "");
}

export default function Home() {
  const [authed, setAuthed] = useState<boolean | null>(null);
  const [password, setPassword] = useState("");
  const [authError, setAuthError] = useState(false);

  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [nextBookingDate, setNextBookingDate] = useState<string>("");
  const [lastBooking, setLastBooking] = useState<LastBooking | null>(null);
  const [upcomingBookings, setUpcomingBookings] = useState<Booking[]>([]);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState(false);
  const [booking, setBooking] = useState(false);
  const [bookingResult, setBookingResult] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/status")
      .then((res) => {
        if (res.ok) {
          setAuthed(true);
          return res.json();
        }
        setAuthed(false);
        setLoading(false);
        return null;
      })
      .then((data) => {
        if (data) {
          setEnabled(data.enabled);
          setNextBookingDate(data.nextBookingDate);
          setLastBooking(data.lastBooking);
          setLoading(false);
        }
      })
      .catch(() => {
        setAuthed(false);
        setLoading(false);
      });
  }, []);

  // Fetch upcoming bookings
  useEffect(() => {
    if (!authed) return;
    fetch("/api/bookings")
      .then((res) => res.ok ? res.json() : { bookings: [] })
      .then((data) => setUpcomingBookings(data.bookings || []))
      .catch(() => setUpcomingBookings([]));
  }, [authed]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError(false);
    const res = await fetch("/api/auth", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    if (res.ok) {
      setAuthed(true);
      setPassword("");
      const statusRes = await fetch("/api/status");
      if (statusRes.ok) {
        const data = await statusRes.json();
        setEnabled(data.enabled);
        setNextBookingDate(data.nextBookingDate);
        setLastBooking(data.lastBooking);
      }
      setLoading(false);
    } else {
      setAuthError(true);
    }
  };

  const handleToggle = async () => {
    if (enabled === null || toggling) return;
    setToggling(true);
    try {
      const res = await fetch("/api/toggle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: !enabled }),
      });
      const data = await res.json();
      setEnabled(data.enabled);
    } catch {
      console.error("Failed to toggle");
    } finally {
      setToggling(false);
    }
  };

  const handleBookNow = async () => {
    if (booking) return;
    setBooking(true);
    setBookingResult("Starting...");
    try {
      const res = await fetch("/api/book-now", { method: "POST" });
      if (!res.ok) {
        setBookingResult("Failed to trigger workflow");
        setBooking(false);
        return;
      }
      setBookingResult("Booking in progress...");

      // Poll workflow status every 10s for up to 5 minutes
      for (let i = 0; i < 30; i++) {
        await new Promise((r) => setTimeout(r, 10000));
        try {
          const statusRes = await fetch("/api/workflow-status");
          const statusData = await statusRes.json();

          if (statusData.status === "completed") {
            if (statusData.conclusion === "success" && statusData.lastBooking?.status === "success") {
              const court = statusData.lastBooking.court || "Court";
              setBookingResult(`Booked! ${court}`);
            } else if (statusData.conclusion === "success") {
              setBookingResult("Completed — no slots available");
            } else {
              setBookingResult(`Failed (${statusData.conclusion || "unknown"})`);
            }
            // Refresh bookings list
            fetch("/api/bookings")
              .then((r) => r.ok ? r.json() : { bookings: [] })
              .then((d) => setUpcomingBookings(d.bookings || []));
            setBooking(false);
            return;
          }
          setBookingResult(`Booking in progress... (${Math.floor((i + 1) * 10 / 60)}m ${((i + 1) * 10) % 60}s)`);
        } catch {
          // Keep polling
        }
      }
      setBookingResult("Timed out — check GitHub Actions");
    } catch {
      setBookingResult("Failed to trigger workflow");
    } finally {
      setBooking(false);
    }
  };

  if (authed === null || (authed && loading)) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <div className="animate-pulse text-zinc-500 text-lg">Loading...</div>
      </main>
    );
  }

  if (!authed) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center px-6 gap-6">
        <div className="text-center space-y-1">
          <h1 className="text-2xl font-bold tracking-tight">PickleBook</h1>
          <p className="text-zinc-500 text-sm">Enter password to continue</p>
        </div>
        <form onSubmit={handleLogin} className="w-full max-w-xs space-y-4">
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password"
            autoFocus
            className="w-full px-4 py-3 rounded-xl bg-zinc-800 border border-zinc-700 text-white placeholder-zinc-500 focus:outline-none focus:border-pickle focus:ring-1 focus:ring-pickle"
          />
          {authError && (
            <p className="text-red-400 text-sm text-center">Wrong password</p>
          )}
          <button
            type="submit"
            className="w-full py-3 rounded-xl bg-pickle text-white font-semibold hover:bg-pickle-dark active:scale-[0.98] transition-all"
          >
            Enter
          </button>
        </form>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen flex-col items-center px-6 py-12 gap-8">
      {/* Header */}
      <div className="text-center space-y-1">
        <h1 className="text-2xl font-bold tracking-tight">PickleBook</h1>
        <p className="text-zinc-500 text-sm">Fremont courts</p>
      </div>

      {/* Toggle */}
      <div className="flex flex-col items-center gap-5">
        <button
          onClick={handleToggle}
          disabled={toggling}
          role="switch"
          aria-checked={enabled ?? false}
          className={`
            relative w-28 h-14 rounded-full transition-colors duration-300
            ${toggling ? "opacity-60 cursor-wait" : "cursor-pointer"}
            ${enabled ? "bg-pickle" : "bg-zinc-700"}
          `}
        >
          <span
            className={`
              absolute top-1.5 left-1.5 w-11 h-11 rounded-full bg-white shadow-md
              transition-transform duration-300
              ${enabled ? "translate-x-14" : "translate-x-0"}
            `}
          />
        </button>

        <div className="text-center space-y-1">
          <p className="text-lg font-medium">
            {enabled ? (
              <span className="text-pickle">Auto-book ON</span>
            ) : (
              <span className="text-zinc-400">Auto-book OFF</span>
            )}
          </p>
          <p className="text-zinc-500 text-sm">
            Next: <span className="text-zinc-300">{nextBookingDate}</span>
          </p>
        </div>
      </div>

      {/* Last Booking Result */}
      {lastBooking && (
        <div className={`w-full max-w-xs rounded-xl p-4 ${
          lastBooking.status === "success" ? "bg-pickle/10 border border-pickle/30" : "bg-red-500/10 border border-red-500/30"
        }`}>
          <p className="text-xs text-zinc-500 uppercase tracking-wide mb-1">Last Booking</p>
          <p className={`font-semibold ${lastBooking.status === "success" ? "text-pickle" : "text-red-400"}`}>
            {lastBooking.status === "success" ? "Booked" : "Failed"}
          </p>
          {lastBooking.court && (
            <p className="text-sm text-zinc-300 mt-1">{lastBooking.court}</p>
          )}
          <p className="text-sm text-zinc-400">{lastBooking.date}</p>
        </div>
      )}

      {/* Upcoming Bookings */}
      <div className="w-full max-w-xs">
        <p className="text-xs text-zinc-500 uppercase tracking-wide mb-3">Upcoming Bookings</p>
        {upcomingBookings.length === 0 ? (
          <p className="text-zinc-600 text-sm">No bookings</p>
        ) : (
          <div className="space-y-2">
            {upcomingBookings.map((b, i) => (
              <div key={i} className="bg-zinc-800/50 rounded-lg p-3 border border-zinc-700/50 flex justify-between items-center">
                <div>
                  <p className="text-sm font-medium text-zinc-200">{formatDate(b.date)}</p>
                  <p className="text-xs text-zinc-400">{b.time}</p>
                </div>
                <div className="text-right">
                  <p className="text-sm text-pickle font-medium">{formatCourt(b.court)}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Book Now */}
      <div className="flex flex-col items-center gap-3 w-full max-w-xs mt-2">
        <button
          onClick={handleBookNow}
          disabled={booking}
          className={`
            w-full py-3.5 px-6 rounded-xl font-semibold text-sm tracking-wide transition-all
            ${booking
              ? "bg-zinc-700 text-zinc-400 cursor-wait"
              : "bg-zinc-800 text-white hover:bg-zinc-700 active:scale-[0.98]"
            }
          `}
        >
          {booking ? "Triggering..." : "Book Now"}
        </button>

        {bookingResult && (
          <p className={`text-sm text-center ${
            bookingResult.includes("success") ? "text-pickle" : "text-red-400"
          }`}>
            {bookingResult}
          </p>
        )}
      </div>
    </main>
  );
}
