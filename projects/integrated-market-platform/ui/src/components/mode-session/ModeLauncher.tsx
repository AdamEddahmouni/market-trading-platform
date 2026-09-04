import { useRef, useState } from "react";
import { LiveModeConfirmation } from "./LiveModeConfirmation";
import { MODE_LAUNCH_ORDER, modeMetadata } from "./modeMetadata";
import type { Mode } from "./types";

type Props = {
  onSelect: (mode: Mode) => void;
};

const modes = MODE_LAUNCH_ORDER.map((mode) => modeMetadata(mode));

export function ModeLauncher({ onSelect }: Props) {
  const [liveConfirmationOpen, setLiveConfirmationOpen] = useState(false);
  const liveButtonRef = useRef<HTMLButtonElement>(null);

  return (
    <main className="mode-session mode-session-launcher">
      <section className="mode-launch-deck" aria-labelledby="mode-launcher-heading">
        <header className="mode-launch-header">
          <p className="mode-session-eyebrow">Initialize session</p>
          <h1 id="mode-launcher-heading">Choose how you enter the market.</h1>
          <p>
            Set the environment for this session. You can switch modes later without leaving the
            workstation.
          </p>
        </header>
        <div className="mode-card-grid">
          {modes.map(({ id: mode, label, descriptor, launchCopy }) => (
            <button
              key={mode}
              type="button"
              className="mode-card"
              data-mode={mode}
              ref={mode === "LIVE" ? liveButtonRef : undefined}
              onClick={() => {
                if (mode === "LIVE") {
                  setLiveConfirmationOpen(true);
                  return;
                }
                onSelect(mode);
              }}
            >
              <span className="mode-card-index">{mode === "DEMO" ? "D" : mode === "PAPER" ? "P" : "L"}</span>
              <span className="mode-card-title">{label}</span>
              <span className="mode-card-descriptor">{descriptor}</span>
              <span className="mode-card-copy">{launchCopy}</span>
              <span className="mode-card-action">Enter environment</span>
            </button>
          ))}
        </div>
      </section>
      <LiveModeConfirmation
        open={liveConfirmationOpen}
        triggerRef={liveButtonRef}
        onCancel={() => setLiveConfirmationOpen(false)}
        onConfirm={() => {
          setLiveConfirmationOpen(false);
          onSelect("LIVE");
        }}
      />
    </main>
  );
}
