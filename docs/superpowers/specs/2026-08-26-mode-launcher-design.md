# Mode Launcher Design

**Date:** 2026-08-26
**Status:** Approved design, pending written-spec review
**Scope:** First-launch mode selection, startup progress, Live confirmation, temporary mode dashboards, and mode switching

## Purpose

The application must begin each fresh load with an explicit operating-environment choice. The operator selects Demo, Paper, or Live before entering the workstation. This phase establishes that entry flow and its safety semantics without prematurely designing the final dashboards.

The launcher has one job: make the current environment unmistakable before the operator enters the application.

## Product decisions

- The launcher appears on every fresh application load. No mode is persisted across reloads or restarts.
- A persistent **Switch mode** control is available after entry from every temporary dashboard.
- Demo and Paper launch immediately after selection.
- Live means **read-only live market data**, not live trade execution.
- Live requires an explicit second confirmation after the initial Live-card selection.
- Live trading is outside this feature. A future live-execution capability will be a separate in-platform control with independent authorization and safeguards.
- Each mode initially opens a simple mode-specific placeholder dashboard. Final dashboards will be designed and implemented separately, piece by piece.

## Visual direction: Signal at Open

The approved launcher uses the three-card **Launch Deck** structure with a visual identity combining the precision of the explored Signal Room direction and the atmosphere of the Opening Bell direction.

The screen uses a deep exchange-blue environment, a restrained market grid, warm light near the upper-right horizon, and semantic edge colors on the three mode cards. Demo uses neutral blue-gray, Paper uses green, and Live uses amber. The previously explored heartbeat/ticker line is explicitly excluded.

Typography is compact and operational for status metadata, paired with a larger, tightly spaced interface heading. The cards remain the dominant interaction and receive the visual emphasis. Animation is concentrated in application startup, environment transitions, and small card interactions; decorative ambient motion must remain restrained.

Approved primary copy:

- Eyebrow: **Initialize session**
- Heading: **Choose how you enter the market.**
- Supporting text: **Set the environment for this session. You can switch modes later without leaving the workstation.**
- Demo: **Explore historical market conditions with replay data and no execution.**
- Paper: **Practice decisions and place simulated orders against market data.**
- Live: **Watch current market data. Order execution remains locked by default.**

The layout must remain usable on narrow mobile viewports, where the cards stack vertically. Keyboard focus must be clearly visible, and reduced-motion preferences must be respected.

## Experience flow

### Fresh launch

1. The application renders its startup experience.
2. Startup reports actual readiness stages.
3. When the required UI and platform readiness checks finish, the launcher appears.
4. No environment is preselected.

### Demo

1. The operator selects Demo.
2. A short Demo transition reports real environment-loading stages.
3. The Demo placeholder dashboard opens with Demo visibly identified as the active mode.

### Paper

1. The operator selects Paper.
2. A short Paper transition reports real environment-loading stages.
3. The Paper placeholder dashboard opens with Paper visibly identified as the active mode.

### Live

1. The operator selects Live.
2. A modal dialog asks: **Enter the live-data environment?**
3. The dialog states that current provider data may be displayed and that this action does not enable live trading, place orders, or grant execution authority.
4. The authority summary displays `Data environment: LIVE` and `Execution authority: LOCKED`.
5. **Go back** closes the dialog and restores focus to the Live card.
6. **Enter live data** begins the Live transition and opens the Live placeholder dashboard.

### Switching modes

1. The operator selects **Switch mode** from a placeholder dashboard.
2. The application clears the in-memory mode selection and returns to the full launcher.
3. The operator makes a fresh selection. Live always requires confirmation, including when reached through Switch mode.

Refreshing or reopening the application also clears the selection and returns to startup followed by the launcher.

## Loading and progress model

Loading feedback must describe actual work rather than display fabricated progress.

Application startup uses these user-facing stages where supported by real readiness signals:

1. **Starting interface**
2. **Connecting to platform**
3. **Checking environment readiness**
4. **Ready**

Rules:

- Measurable work uses determinate percentage progress.
- Work whose completion percentage is unknown uses an indeterminate progress bar and a plain-language status.
- Mode transitions show completed, active, and pending stages for the selected environment.
- Slow component-level data uses skeleton states.
- Small isolated actions use inline activity indicators rather than blocking the entire interface.
- Completion is never intentionally delayed to prolong an animation.
- Reduced-motion mode removes nonessential transforms and uses simple opacity or immediate state changes.

If startup or a mode transition fails, the progress surface remains visible and identifies the failed stage. It provides **Retry** and **Return to mode selection** actions where returning is possible. Errors must state what failed and what the operator can do next.

## Component architecture

### `ApplicationBootstrap`

Owns application readiness and startup-progress presentation. It gates the launcher until required UI initialization and platform connectivity checks have resolved. A failed readiness check renders the startup error state rather than falling through to a misleading ready screen.

### `ModeSessionProvider`

Owns the current `DEMO | PAPER | LIVE | null` selection in React memory. It does not write the selection to local storage, session storage, cookies, URL parameters, or backend state. A fresh application mount therefore begins with `null`.

### `ModeLauncher`

Renders the approved Signal at Open screen and the Demo, Paper, and Live cards. It requests a mode change but does not itself mutate execution authority or connect brokers.

### `LiveModeConfirmation`

Provides the mandatory modal confirmation for Live. It owns dialog focus management, cancellation, and the explicit confirmation event. The dialog must be operable by keyboard and announced with the correct accessible dialog semantics.

### `ModeTransition`

Displays honest loading state while the application prepares the selected placeholder environment. It consumes readiness steps supplied by the relevant environment adapter rather than inventing percentages.

### `ModePlaceholderDashboard`

Renders minimal, visibly distinct Demo, Paper, and Live destinations. Each destination includes the active mode, a short statement of its authority boundary, and the Switch mode control. It contains no attempt at the final dashboard information architecture.

### `SwitchModeControl`

Clears the current in-memory selection and returns to the launcher. It does not retain a default or bypass Live confirmation.

## Data flow and integration boundary

The initial state path is:

`ApplicationBootstrap → ModeLauncher → optional LiveModeConfirmation → ModeTransition → ModePlaceholderDashboard`

The existing workstation shell remains behind this gate and is not redesigned in this phase. The placeholder dashboards provide stable destinations that can later be replaced by individually designed mode dashboards.

Mode selection in this phase is frontend session context only. It must not:

- enable live order execution;
- change backend execution authority;
- connect or authenticate a production broker;
- submit, preview, or stage an order;
- represent read-only provider availability as execution readiness.

The Live placeholder may identify the environment as read-only, but it must not claim that live providers are healthy unless that state comes from an actual provider-readiness response.

## Accessibility and interaction requirements

- All mode cards are native buttons or expose equivalent button semantics and keyboard behavior.
- Focus order follows Demo, Paper, Live.
- Focus is visible against every card state.
- The Live confirmation traps focus while open, closes on Escape, and restores focus to the Live trigger.
- Progress changes use an appropriately polite live region without repeatedly announcing decorative animation frames.
- Color is not the only indicator of mode or authority.
- The interface supports narrow viewports without horizontal scrolling.
- Motion honors `prefers-reduced-motion`.

## Error behavior

- Startup API failure names the failed readiness stage and offers Retry.
- A failed mode transition keeps the selected mode visible and offers Retry or Return to mode selection.
- Retrying reruns the failed readiness work and does not reload the entire browser page unless technically required.
- Live confirmation cannot be bypassed by retry, browser-history navigation, or the Switch mode flow.
- Unknown errors use a stable fallback message and do not expose secrets, tokens, or raw provider payloads.

## Testing strategy

Focused UI tests must cover:

- startup stages advancing from initialization to launcher using controlled readiness results;
- startup failure, Retry, and recovery;
- Demo entering only the Demo placeholder;
- Paper entering only the Paper placeholder;
- Live selection opening the confirmation without entering Live;
- Live cancellation restoring focus to the Live card;
- explicit Live confirmation entering the Live placeholder;
- Switch mode returning to the launcher from all three placeholders;
- Live confirmation recurring after switching back to Live;
- a fresh provider mount containing no remembered mode;
- accessible card names, dialog semantics, focus trapping, Escape behavior, and status announcements;
- reduced-motion behavior and responsive stacking.

Implementation follows test-driven development: add one failing behavior test, confirm the expected failure, implement the smallest passing behavior, and repeat.

Repository validation follows `AGENTS.md`:

1. Run focused UI tests during red-green cycles.
2. Run `.venv\Scripts\python.exe tools\validate.py changed` after implementation edits.
3. Run the relevant UI/domain validation at the milestone if available.
4. Run `.venv\Scripts\python.exe tools\validate.py full` once at the final major checkpoint when the changed-file result requires the full suite.

All validation remains offline; no live-provider validation is required because this feature does not change a live provider boundary.

## Out of scope

- Final Demo, Paper, or Live dashboard design
- Persistent default-mode preferences
- Live-trading enablement or authorization
- Broker authentication or connectivity changes
- Backend execution-mode mutation
- Final navigation redesign inside each environment
- Real provider-health implementation beyond consuming an existing readiness signal

## Acceptance criteria

The feature is ready for implementation acceptance when:

1. Every fresh application mount shows honest startup progress followed by the mode launcher.
2. The launcher matches the approved Signal at Open direction without a heartbeat/ticker line.
3. Demo and Paper enter their respective temporary dashboards.
4. Live cannot be entered without the explicit read-only confirmation.
5. No launcher action can enable or imply live execution authority.
6. Switch mode works from all three temporary dashboards and never remembers a default.
7. Loading, failure, keyboard, mobile, and reduced-motion behaviors satisfy this specification.
8. Focused UI tests and required repository validation pass.
