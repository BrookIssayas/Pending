import type { JobApplication } from "@/lib/api";
import { SplitFlap } from "./SplitFlap";
import styles from "./ApplicationRow.module.css";

const STATUS_CLASS: Record<JobApplication["status"], string> = {
  Applied: styles.neutral,
  Interviewing: styles.progress,
  Rejected: styles.negative,
  Offer: styles.positive,
  Ghosted: styles.neutral,
};

function formatDate(iso: string): string {
  return new Date(iso)
    .toLocaleDateString(undefined, { month: "short", day: "numeric" })
    .toUpperCase();
}

interface ApplicationRowProps {
  application: JobApplication;
  index: number;
}

export function ApplicationRow({ application, index }: ApplicationRowProps) {
  return (
    <div
      className={styles.row}
      style={{ animationDelay: `${index * 40}ms` }}
    >
      <div className={styles.info}>
        <p className={styles.company}>
          {application.company_normalized.toUpperCase()}
        </p>
        <p className={styles.role}>{application.role_title ?? "ROLE UNKNOWN"}</p>
      </div>
      <div className={styles.meta}>
        <span className={styles.date}>
          LAST UPDATE {formatDate(application.last_email_at)}
        </span>
        <SplitFlap
          text={application.status}
          className={STATUS_CLASS[application.status]}
        />
      </div>
    </div>
  );
}
