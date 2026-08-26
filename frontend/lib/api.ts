import { supabase } from "./supabase-client";

const API_BASE_URL = process.env.API_BASE_URL;

if (!API_BASE_URL) {
  throw new Error("Missing API_BASE_URL. Check .env.local.");
}

export type ApplicationStatus =
  | "Applied"
  | "Interviewing"
  | "Rejected"
  | "Offer"
  | "Ghosted";

export interface JobApplication {
  id: string;
  user_id: string;
  company_normalized: string;
  role_title: string | null;
  status: ApplicationStatus;
  last_email_at: string;
  created_at: string;
  updated_at: string;
}

export class NotAuthenticatedError extends Error {
  constructor() {
    super("Not authenticated");
    this.name = "NotAuthenticatedError";
  }
}

export async function fetchApplications(
  status?: ApplicationStatus
): Promise<JobApplication[]> {
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    throw new NotAuthenticatedError();
  }

  const url = new URL(`${API_BASE_URL}/applications`);
  if (status) {
    url.searchParams.set("status", status);
  }

  const response = await fetch(url.toString(), {
    headers: {
      Authorization: `Bearer ${session.access_token}`,
    },
  });

  if (response.status === 401) {
    throw new NotAuthenticatedError();
  }

  if (!response.ok) {
    throw new Error(`Failed to fetch applications: ${response.status}`);
  }

  return response.json();
}
