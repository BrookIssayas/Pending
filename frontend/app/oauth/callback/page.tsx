
import { Suspense } from "react";
import { CallbackHandler } from "./callbackHandler";

export default function OAuthCallbackPage() {
  return (
    <Suspense fallback={<main><p>Completing sign-in…</p></main>}>
      <CallbackHandler />
    </Suspense>
  );
}