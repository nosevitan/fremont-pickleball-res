"use client";

import { useState, useEffect, useCallback } from "react";

export default function Home() {
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [nextBookingDate, setNextBookingDate] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState(false);
  const [booking, setBooking] = useState(false);
  const [bookingResult, setBookingResult] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch("/api/status");
      const data = await res.json();
      setEnabled(data.enabled);
      setNextBookingDate(data.nextBookingDate);
    } catch {
      console.error("Failed to fetch status");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

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

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <div className="animate-pulse text-zinc-500 text-lg">Loading...</div>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-6 py-12 gap-10">
      {/* Header */}
      <div className="text-center space-y-1">
        <h1 className="text-2xl font-bold tracking-tight">
          Pickleball Auto-Booker
        </h1>
        <p className="text-zinc-500 text-sm">Fremont courts</p>
      </div>

      {/* Toggle */}
      <div className="flex flex-col items-center gap-6">
        <button
          onClick={handleToggle}
          disabled={toggling}
          aria-label={`Auto-booking is ${enabled ? "enabled" : "disabled"}. Click to ${enabled ? "disable" : "enable"}.`}
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

        {/* Status */}
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

      {/* Book Now */}
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
            className={`text-sm text-center animate-fade-in ${
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
