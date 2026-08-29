"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase-client";
import {
  fetchApplications,
  NotAuthenticatedError,
  type JobApplication,
} from "@/lib/api";
import { StatusTabs, type StatusFilter } from "@/components/StatusTabs";
import { ApplicationRow } from "@/components/ApplicationRow";
import styles from "./dashboard.module.css";

const STATUSES: StatusFilter[] = [
  "All",
  "Applied",
  "Interviewing",
  "Rejected",
  "Offer",
  "Ghosted",
];

export default function DashboardPage() {
  const router = useRouter();
  const [applications, setApplications] = useState<JobApplication[]>([]);
  const [activeStatus, setActiveStatus] = useState<StatusFilter>("All");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    async (status: StatusFilter) => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchApplications(
          status === "All" ? undefined : status
        );
        setApplications(data);
      } catch (err) {
        if (err instanceof NotAuthenticatedError) {
          router.replace("/login");
          return;
        }
        setError("Could not load applications. Try again shortly.");
      } finally {
        setLoading(false);
      }
    },
    [router]
  );

  useEffect(() => {
    load(activeStatus);
  }, [activeStatus, load]);

  const handleSignOut = async () => {
    await supabase.auth.signOut();
    router.replace("/login");
  };

  return (
    <main className={styles.wrap}>
      <header className={styles.header}>
        <div>
          <h1 className={styles.wordmark}>Pending</h1>
        </div>
        <button type="button" className={styles.signOut} onClick={handleSignOut}>
          SIGN OUT
        </button>
      </header>

      <StatusTabs
        statuses={STATUSES}
        active={activeStatus}
        onChange={setActiveStatus}
      />

      <section className={styles.board}>
        {loading && <p className={styles.message}>LOADING…</p>}
        {!loading && error && <p className={styles.message}>{error.toUpperCase()}</p>}
        {!loading && !error && applications.length === 0 && (
          <p className={styles.message}>NO ENTRIES</p>
        )}
        {!loading &&
          !error &&
          applications.map((app, i) => (
            <ApplicationRow key={app.id} application={app} index={i} />
          ))}
      </section>
    </main>
  );
}
