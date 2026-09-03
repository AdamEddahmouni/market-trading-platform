# IBKR desktop Gateway observational upgrade

## Status

Approved design for implementation. This change adds an optional TWS socket
transport for the already-running desktop IB Gateway while retaining the
existing Client Portal Gateway REST transport.

## Goal

Allow the existing `tools/ibkr` capability probe and observational capture
boundary to connect to the local desktop IB Gateway at `127.0.0.1:4001`.
The connection must remain read-only, loopback-only, explicitly gated, and
value-blind in reports and evidence.

## Chosen approach

Add an optional TWS socket adapter backed by `ib_insync`, isolated under
`tools/ibkr`. The adapter will be loaded only when the TWS transport is
selected; the default transport remains Client Portal REST. The dependency
will be optional and documented separately so the existing standard-library
runtime path and offline validation remain dependency-free.

The adapter will present the same restricted capability interface consumed by
`CapabilityProbe`. It will translate only the existing observational
operations:

- connection/authentication status;
- stock contract lookup;
- market-data snapshot;
- historical bars;
- option-definition lookup;
- scanner-parameter availability; and
- portfolio-read availability.

It will not expose `placeOrder`, order modification, cancellation, account
funding, or any other mutation method.

## Configuration and selection

Add explicit transport configuration:

- `IMP_IBKR_TRANSPORT=client_portal` by default;
- `IMP_IBKR_TRANSPORT=tws` to select the desktop Gateway;
- `IMP_IBKR_TWS_HOST=127.0.0.1`;
- `IMP_IBKR_TWS_PORT=4001` by default, with 4002 available only for an
  explicitly configured paper Gateway; and
- `IMP_IBKR_TWS_CLIENT_ID` with a safe nonzero default and validation.

`IMP_IBKR_LIVE=1` remains required for either transport. TWS configuration
must reject non-loopback hosts and invalid ports before importing or
constructing the socket client. Client Portal URL validation remains unchanged.

The TWS adapter uses the operator-authenticated desktop Gateway session; no
IBKR username, password, or second-factor secret is read by this path.

## Data flow

```text
tools/ibkr/probe.py
        |
        v
transport factory selected by IbkrConfig
   |                         |
   v                         v
Client Portal REST       TWS socket adapter
   |                         |
   +------------+------------+
                v
restricted capability interface
                v
redacted CAPTURED_NOT_ADMITTED evidence
```

The probe will identify the selected transport and provider in its
value-blind report. Raw broker payloads will not be copied into capability
reports. TWS observations will use the existing redaction and append-only
capture boundary, with account identifiers and credentials removed.

## Error handling and lifecycle

- Missing `ib_insync` produces a sanitized setup error and no socket attempt.
- A closed port, duplicate client ID, disconnected Gateway, or rejected
  request produces an observed error for the affected capability.
- One failed capability does not suppress independent capability checks.
- Socket connect, request, and disconnect operations remain bounded by
  configuration timeouts.
- The adapter disconnects in a `finally` path after a probe or bounded
  collection.
- No automatic reconnect loop will be added in this first upgrade.
- TWS pacing is client-enforced conservatively; the adapter will not retry
  failed requests in a way that can amplify broker traffic.

## Safety boundary

The TWS module will be covered by AST/text safety tests that reject:

- order submission, modification, and cancellation symbols;
- fund movement or execution authority symbols;
- non-loopback endpoints;
- credential logging or persistence; and
- unbounded generic socket/request escape hatches.

`IMP_IBKR_LIVE=1` is an observational opt-in, not execution authority.
Existing repository invariants continue to block live production execution.

## Testing and verification

Tests will be written before implementation and will cover:

1. TWS configuration defaults, loopback enforcement, port/client-ID validation,
   and transport selection.
2. Adapter behavior through injected fake broker objects, including
   normalization of contract, quote, history, option, scanner, and portfolio
   availability results.
3. Missing dependency, disconnected session, rejected request, and partial
   capability failures.
4. Redaction of account identifiers, credentials, and broker payloads.
5. Safety rejection of order-like or non-loopback behavior.
6. CLI selection of TWS versus Client Portal without live calls when the gate
   is disabled.

Offline tests will use fakes only. A separate opt-in live verification will
run against the user's connected `127.0.0.1:4001` Gateway and will write only
sanitized local evidence. No ordinary validation command will contact IBKR.

## Out of scope

- live order execution or paper-order submission;
- Level-2/depth claims beyond the account's entitlements;
- a generic IBKR SDK surface;
- automatic username/password/TOTP login;
- WAN or remote Gateway access;
- historical admission into the research dataset; and
- replacing the existing Client Portal implementation.

## Acceptance criteria

The upgrade is accepted when:

- `IMP_IBKR_TRANSPORT=tws` reaches the connected desktop Gateway on port 4001;
- the existing capability report completes through the TWS adapter with
  sanitized observed/untested statuses;
- the default Client Portal path remains backward-compatible;
- offline IBKR tests and changed validation pass; and
- no order or execution path is introduced.
