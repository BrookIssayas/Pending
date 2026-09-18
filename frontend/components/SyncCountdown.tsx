// components/SyncCountdown.tsx
// CHANGED: once the countdown hits zero, polls next-refresh every 30s
// until last_synced_at actually advances, instead of freezing on
// "syncing now" indefinitely.

"use client";

import { useEffect, useRef, useState } from "react";
import { fetchNextSyncTime } from "@/lib/api";
import { supabase } from "@/lib/supabase-client";

const POLL_INTERVAL_MS = 30_000;

function formatRemaining(ms: number): string {
  if (ms <= 0) return "syncing now";
  const totalSeconds = Math.floor(ms / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return [hours, minutes, seconds]
    .map((n) => String(n).padStart(2, "0"))
    .join(":");
}

export function SyncCountdown() {
  const [nextSyncAt, setNextSyncAt] = useState<Date | null>(null);
  const [lastSyncedAt, setLastSyncedAt] = useState<string | null>(null);
  const [remaining, setRemaining] = useState<string>("");
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refetch = async () => {
    console.log((await supabase.auth.getSession()).data.session?.access_token)
    fetchNextSyncTime()
      .then((data) => {
        setNextSyncAt(new Date(data.next_sync_at));
        setLastSyncedAt((prev) => {
          if (data.last_synced_at && data.last_synced_at !== prev) {
            // sync actually advanced — stop polling
            if (pollingRef.current) {
              clearInterval(pollingRef.current);
              pollingRef.current = null;
            }
          }
          return data.last_synced_at;
        });
      })
      .catch(() => {
        // leave state as-is — don't clear a valid timer over a transient fetch error
      });
  };

  useEffect(() => {
    refetch();
  }, []);

  useEffect(() => {
    if (!nextSyncAt) return;

    const tick = () => {
      const ms = nextSyncAt.getTime() - Date.now();
      setRemaining(formatRemaining(ms));

      if (ms <= 0 && !pollingRef.current) {
        pollingRef.current = setInterval(refetch, POLL_INTERVAL_MS);
      }
    };

    tick();
    const interval = setInterval(tick, 1000);
    return () => {
      clearInterval(interval);
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [nextSyncAt]);

  if (!nextSyncAt) return null;

  return (
    <div className="text-sm text-muted-foreground">
      Next refresh: {remaining}
    </div>
  );
}