"use client";

import { useState, useEffect, useCallback } from "react";

export default function Home() {
  const [authed, setAuthed] = useState<boolean | null>(null);
  const [password, setPassword] = useState("");
  const [authError, setAuthError] = useState(false);

  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [nextBookingDate, setNextBookingDate] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState(false);
  const [booking, setBooking] = useState(false);
  const [bookingResult, setBookingResult] = useState<string | null>(null);

  // Check if already authed by trying to hit the status endpoint
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
          setLoading(false);
        }
      })
      .catch(() => {
        setAuthed(false);
        setLoading(false);
      });
  }, []);

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
      // Fetch status after auth
      const statusRes = await fetch("/api/status");
      if (statusRes.ok) {
        const data = await statusRes.json();
        setEnabled(data.enabled);
        setNextBookingDate(data.nextBookingDate);
      }
      setLoading(false);
    } else {
      setAuthError(true);
    }
  };

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch("/api/status");
      const data = await res.json();
      setEnabled(data.enabled);
      setNextBookingDate(data.nextBookingDate);
    } catch {
      console.error("Failed to fetch status");
    }
  }, []);

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
    setBookingResult(null);
    try {
      const res = await fetch("/api/book-now", { method: "POST" });
      if (res.ok) {
        setBookingResult("Workflow triggered successfully");
      } else {
        setBookingResult("Failed to trigger workflow");
      }
    } catch {
      setBookingResult("Failed to trigger workflow");
    } finally {
      setBooking(false);
      setTimeout(() => setBookingResult(null), 4000);
    }
  };

  // Loading
  if (authed === null || (authed && loading)) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <div className="animate-pulse text-zinc-500 text-lg">Loading...</div>
      </main>
    );
  }

  // Password screen
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

  // Main app
  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-6 py-12 gap-10">
      <div className="text-center space-y-1">
        <h1 className="text-2xl font-bold tracking-tight">
          Pickleball Auto-Booker
        </h1>
        <p className="text-zinc-500 text-sm">Fremont courts</p>
      </div>

      <div className="flex flex-col items-center gap-6">
        <button
          onClick={handleToggle}
          disabled={toggling}
          aria-label={`Auto-booking is ${enabled ? "enabled" : "disabled"}.`}
          role="switch"
          aria-checked={enabled ?? false}
          className={`
            relative w-28 h-14 rounded-full transition-colors duration-300 ease-in-out
            focus:outline-none focus-visible:ring-4 focus-visible:ring-pickle/40
            ${toggling ? "opacity-60 cursor-wait" : "cursor-pointer"}
            ${enabled ? "bg-pickle" : "bg-zinc-700"}
          `}
        >
          <span
            className={`
              absolute top-1.5 left-1.5 w-11 h-11 rounded-full bg-white shadow-md
              transition-transform duration-300 ease-in-out
              ${enabled ? "translate-x-14" : "translate-x-0"}
            `}
          />
        </button>

        <div className="text-center space-y-2">
          <p className="text-lg font-medium">
            {enabled ? (
              <span className="text-pickle">Enabled</span>
            ) : (
              <span className="text-zinc-400">Disabled</span>
            )}
          </p>
          <p className="text-zinc-500 text-sm">
            Next booking: <span className="text-zinc-300">{nextBookingDate}</span>
          </p>
        </div>
      </div>

      <div className="flex flex-col items-center gap-3 w-full max-w-xs">
        <button
          onClick={handleBookNow}
          disabled={booking}
          className={`
            w-full py-3.5 px-6 rounded-xl font-semibold text-sm tracking-wide
            transition-all duration-200
            focus:outline-none focus-visible:ring-4 focus-visible:ring-pickle/40
            ${booking
              ? "bg-zinc-700 text-zinc-400 cursor-wait"
              : "bg-zinc-800 text-white hover:bg-zinc-700 active:scale-[0.98]"
            }
          `}
        >
          {booking ? "Triggering..." : "Book Now"}
        </button>

        {bookingResult && (
          <p
            className={`text-sm text-center ${
              bookingResult.includes("success")
                ? "text-pickle"
                : "text-red-400"
            }`}
          >
            {bookingResult}
          </p>
        )}
      </div>
    </main>
  );
}
