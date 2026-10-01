import { useEffect, useRef, useState } from "react";
import { api } from "../../api/endpoints";

type Phase = "idle" | "confirm" | "stopping" | "stopped" | "failed";

/**
 * Stops the local platform (API, UI dev server, control service) from inside the app.
 * Asks once inline, then replaces the page with a "stopped" notice, since every request
 * fails after the services exit. Start again from the desktop shortcut.
 */
export function ExitPlatformButton({ className }: { className?: string }) {
  const [phase, setPhase] = useState<Phase>("idle");
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (phase === "confirm") confirmRef.current?.focus();
  }, [phase]);

  const stop = async () => {
    setPhase("stopping");
    try {
      await api.runOperatorLifecycleAction("stop");
      setPhase("stopped");
    } catch {
      setPhase("failed");
    }
  };

  if (phase === "stopped") {
    return <div className="imp-exit-overlay" role="alertdialog" aria-modal="true" aria-labelledby="imp-exit-title">
      <div className="imp-exit-card">
        <h2 id="imp-exit-title">Platform stopped</h2>
        <p>The platform is shutting down. You can close this tab.</p>
        <p>To start it again, open <strong>Market Platform</strong> on the desktop.</p>
      </div>
    </div>;
  }

  if (phase === "confirm" || phase === "stopping" || phase === "failed") {
    return <span className="imp-exit-confirm" role="group" aria-label="Stop the platform">
      <span className="imp-exit-question">{phase === "failed" ? "Stop failed. Retry?" : "Stop the platform?"}</span>
      <button ref={confirmRef} type="button" className={className} disabled={phase === "stopping"} onClick={() => void stop()}>
        {phase === "stopping" ? "Stopping…" : "Stop"}
      </button>
      <button type="button" className={className} disabled={phase === "stopping"} onClick={() => setPhase("idle")}>Cancel</button>
    </span>;
  }

  return <button type="button" className={className} title="Stop the platform and its data feeds"
    onClick={() => setPhase("confirm")}>Exit</button>;
}
