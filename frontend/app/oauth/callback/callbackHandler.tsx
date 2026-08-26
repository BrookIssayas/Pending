// app/oauth/callback/CallbackHandler.tsx

"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { supabase } from "@/lib/supabase-client";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL!;

export function CallbackHandler() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const code = searchParams.get("code");
    if (!code) {
      setError("Please allow Google permissions when logging in.");
      return;
    }

    const redirectUrl = `${window.location.origin}/oauth/callback`;

    async function exchangeCode() {
      try {
        const res = await fetch(`${API_BASE}/auth/oauth/callback`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ provider: "google", code, redirect_url: redirectUrl }),
        });

        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        const data = await res.json();
        const { access_token, refresh_token } = data.token;

        const { error: sessionError } = await supabase.auth.setSession({
          access_token,
          refresh_token,
        });
        if (sessionError) throw sessionError;

        router.replace("/dashboard");
      } catch (err) {
        setError("Authentication failed. Please try again.");
      }
    }

    exchangeCode();
  }, [searchParams, router]);

  if (error) {
    return (
      <main>
        <p>{error}</p>
        <button onClick={() => router.replace("/login")}>Back to login</button>
      </main>
    );
  }

  return (
    <main>
      <p>Completing sign-in…</p>
    </main>
  );
}