"use client";

import type { ApplicationStatus } from "@/lib/api";
import styles from "./StatusTabs.module.css";

export type StatusFilter = ApplicationStatus | "All";

interface StatusTabsProps {
  statuses: StatusFilter[];
  active: StatusFilter;
  onChange: (status: StatusFilter) => void;
}

export function StatusTabs({ statuses, active, onChange }: StatusTabsProps) {
  return (
    <nav className={styles.tabs} aria-label="Filter by status">
      {statuses.map((status) => (
        <button
          key={status}
          type="button"
          className={`${styles.tab} ${active === status ? styles.active : ""}`}
          aria-current={active === status}
          onClick={() => onChange(status)}
        >
          {status.toUpperCase()}
        </button>
      ))}
    </nav>
  );
}
