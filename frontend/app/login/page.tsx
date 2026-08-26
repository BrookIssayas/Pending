"use client";

import { useState } from "react";
import styles from "./login.module.css";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL!;

export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSignIn = async () => {
    setLoading(true);
    setError(null);

    try {
      const redirectUrl = `${window.location.origin}/oauth/callback`;
      
      const res = await fetch(`${API_BASE}/auth/oauth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: "google",
          redirect_url: redirectUrl,
        }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const data = await res.json();

      window.location.href = data.auth_url; // hand off to Google
    } catch (err) {
      setLoading(false);
      setError("Sign-in failed. Please try again.");
    }
  };

  return (
    <main className={styles.wrap}>
      <div className={styles.panel}>
        <h1 className={styles.wordmark}>Pending</h1>
        <p className={styles.tagline}>
          Every application, tracked until it isn&apos;t pending anymore.
        </p>
        {error && <p className={styles.error}>{error}</p>}
        <button
          type="button"
          className={styles.button}
          onClick={handleSignIn}
          disabled={loading}
        >
          {loading ? "CONNECTING…" : "SIGN IN WITH GOOGLE"}
        </button>
      </div>
    </main>
  );
}