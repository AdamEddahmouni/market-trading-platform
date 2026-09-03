import type {
  WorkspaceCatalystResponse,
  WorkspaceDisclosureResponse,
  WorkspaceFundEtfResponse,
  WorkspaceFuturesResponse,
  WorkspaceInstitutionalFlowResponse,
  WorkspaceLargeTransactionsResponse,
  WorkspaceOptionsResponse,
  WorkspaceOrderBookResponse,
  WorkspaceOrderFlowResponse,
  WorkspaceSqueezeResponse,
} from "../../api/schemas";
import type { Mode } from "../mode-session/types";
import type { WorkspaceLaneModuleId, WorkspaceModuleId } from "./laneRegistry";
import type {
  BuildLaneModeContentArgs,
  LaneModeContent,
  LaneModeContentSection,
  LaneQueryState,
  PaperDecisionHint,
} from "./laneModeContentTypes";

function unavailableSummary(queryState: LaneQueryState, mode: Mode): string {
  if (queryState.phase === "loading") return queryState.message ?? "Loading evidence…";
  if (queryState.phase === "error") {
    return mode === "LIVE"
      ? "Operational lane fetch failed — check provider health and live canary."
      : queryState.message ?? "Evidence request failed.";
  }
  if (queryState.degraded) return queryState.message ?? "Lane bridge unavailable.";
  return queryState.message ?? "No evidence returned.";
}

function demoReplaySections(
  cohortLabel: string,
  interpretBullets: string[],
  limitations: string[],
): LaneModeContentSection[] {
  return [
    {
      title: "Replay framing",
      body: `${cohortLabel} Evidence is historical or fixture-bound — not current broker state.`,
      emphasis: "info",
      bullets: interpretBullets,
    },
    {
      title: "What to inspect",
      body: "Use Explain and Inspector actions on cards below to study signal meaning and provenance.",
      emphasis: "neutral",
    },
    {
      title: "Limitations",
      body: "Demo cannot submit orders or mutate paper sessions.",
      emphasis: "warning",
      bullets: limitations,
    },
  ];
}

function paperDecisionSections(
  hint: PaperDecisionHint,
  readinessBullets: string[],
  instrumentId: string,
  moduleId: WorkspaceLaneModuleId,
): LaneModeContentSection[] {
  const hintLabel =
    hint === "supports"
      ? "Evidence leans supportive for a simulated thesis."
      : hint === "contradicts"
        ? "Evidence leans contradictory — reconsider before drafting."
        : hint === "insufficient"
          ? "Insufficient lane evidence for a confident simulated decision."
          : "Evidence is mixed or observational — confirm manually before drafting.";

  return [
    {
      title: "Decision readiness",
      body: hintLabel,
      emphasis: hint === "contradicts" ? "warning" : hint === "supports" ? "success" : "neutral",
      bullets: readinessBullets,
    },
    {
      title: "Draft workflow",
      body: `Use Draft paper order from lane to seed a MARKET ticket on ${instrumentId}. Side and quantity default to BUY × 1 — you must confirm or edit before submit.`,
      emphasis: "info",
      bullets: [
        `Provenance will carry as lane:${moduleId}.`,
        "Preview revalidates against current paper portfolio and risk limits on the workspace overview.",
        "Stale or invalid drafts fail closed — re-preview after edits.",
      ],
    },
  ];
}

function liveObservationalSections(
  freshnessBullets: string[],
  limitations: string[],
): LaneModeContentSection[] {
  return [
    {
      title: "Broker-observed context",
      body: "Live lane modules are read-only. Nothing here authorizes execution.",
      emphasis: "warning",
      bullets: freshnessBullets,
    },
    {
      title: "Operational limits",
      body: "Treat stale or degraded provider state as observational only.",
      emphasis: "neutral",
      bullets: limitations,
    },
  ];
}

function buildSqueezeContent(args: BuildLaneModeContentArgs): LaneModeContent {
  const data = args.data as WorkspaceSqueezeResponse | null | undefined;
  const cohort =
    args.dataMode === "current" ? "Ephemeral scanner" : "Frozen research cohort";

  if (args.queryState.phase !== "ready" || !data?.available) {
    return {
      headline: args.mode === "DEMO" ? "Squeeze replay context" : args.mode === "PAPER" ? "Squeeze decision context" : "Live squeeze observational",
      summary: unavailableSummary(args.queryState, args.mode),
      sections: [],
      limitations: args.mode === "DEMO" ? ["Historical squeeze states may not reflect current market structure."] : undefined,
      relatedLinks: args.mode === "LIVE" ? [{ label: "Live canary", to: "/live-canary" }] : undefined,
    };
  }

  const ignition = data.ignition_state ?? data.state_machine?.current_state ?? "UNKNOWN";
  const freshness = data.readiness?.freshness_state ?? data.freshness ?? "UNKNOWN";
  const paperHint: PaperDecisionHint =
    ignition === "IGNITED" || ignition === "ACTIVE"
      ? "supports"
      : ignition === "FAILED" || ignition === "EXHAUSTED"
        ? "contradicts"
        : ignition === "WATCH"
          ? "neutral"
          : "insufficient";

  if (args.mode === "DEMO") {
    return {
      headline: "Squeeze replay & interpretation",
      summary: `${cohort} squeeze state: ${ignition}. Freshness ${freshness}.`,
      sections: demoReplaySections(
        cohort,
        [
          `Ignition state ${ignition} — study setup vs ignition criteria in Phase 3A rules below.`,
          data.causal_intelligence?.explanation?.summary
            ? `Causal summary: ${data.causal_intelligence.explanation.summary}`
            : "Open Explain on ignition cards to interpret mechanism labels.",
          data.research_detection ? `Research detection: ${data.research_detection}` : "Cross-check historical context block for cohort limitations.",
        ],
        [
          "Frozen cohort may omit current scanner transitions.",
          "Ignition evidence does not imply tradability in Demo.",
        ],
      ),
      relatedLinks: [{ label: "Workspace overview replay", to: `/workspace/${args.instrumentId}` }],
    };
  }

  if (args.mode === "PAPER") {
    return {
      headline: "Squeeze simulation readiness",
      summary: `Ignition ${ignition}; freshness ${freshness}. Evaluate before drafting a paper order.`,
      decisionHint: paperHint,
      sections: paperDecisionSections(
        paperHint,
        [
          data.readiness?.provenance_admissible
            ? "Provenance admissible for simulation context."
            : "Provenance gated — treat squeeze evidence as lower confidence.",
          data.phase3a_summary ? `Phase 3A: ${data.phase3a_summary}` : "Review Phase 3A rule outcomes in the evidence panel.",
          data.evidence_coverage ? `Coverage: ${data.evidence_coverage}` : "Confirm cross-lane evidence aligns with thesis.",
        ],
        args.instrumentId,
        "squeeze",
      ),
    };
  }

  return {
    headline: "Live squeeze observational",
    summary: `Broker-observed squeeze indicators for ${args.instrumentId}. State label ${data.mode_label ?? "OBSERVED"}.`,
    sections: liveObservationalSections(
      [
        `Reported ignition/state: ${ignition}.`,
        `Freshness signal: ${freshness}.`,
        data.epistemic_class ? `Epistemic class: ${data.epistemic_class}.` : "Treat as observational — aggressor and intent unknown.",
      ],
      ["Live squeeze bridge does not authorize orders.", "Stale squeeze signals may lag broker reality."],
    ),
    relatedLinks: [{ label: "Live canary", to: "/live-canary" }],
  };
}

function orderFlowPaperHint(orderFlow: WorkspaceOrderFlowResponse): PaperDecisionHint {
  const bars = orderFlow.bars ?? [];
  const last = bars[bars.length - 1];
  if (!last) return "insufficient";
  const delta = Number(last.delta ?? 0);
  if (delta > 0) return "supports";
  if (delta < 0) return "contradicts";
  return "neutral";
}

function buildOrderFlowContent(args: BuildLaneModeContentArgs): LaneModeContent {
  const data = args.data as WorkspaceOrderFlowResponse | null | undefined;

  if (args.queryState.phase !== "ready" || !data?.available) {
    return {
      headline: args.mode === "DEMO" ? "Order flow replay" : args.mode === "PAPER" ? "Order flow decision context" : "Live order flow observational",
      summary: unavailableSummary(args.queryState, args.mode),
      sections: [],
      relatedLinks: args.mode === "LIVE" ? [{ label: "Live canary", to: "/live-canary" }] : undefined,
    };
  }

  const bars = data.bars ?? [];
  const last = bars[bars.length - 1];
  const cvd = last ? String(last.cumulative_delta) : "UNKNOWN";
  const provenance = last?.aggressor_provenance ?? "UNKNOWN";

  if (args.mode === "DEMO") {
    return {
      headline: "CVD & signed-volume learning",
      summary: `Fixture CVD ${cvd}. ${data.bar_count ?? bars.length} bars in replay window.`,
      sections: demoReplaySections(
        "Order-flow fixture",
        [
          "CVD aggregates signed volume — inspect bar table for divergence vs price.",
          `Aggressor provenance remains ${provenance} — do not infer intent.`,
          "Compare with order-book depth on the dedicated lane for liquidity context.",
        ],
        ["Fixture entitled for admitted instruments only.", "Unknown aggressor stays unknown in replay."],
      ),
    };
  }

  if (args.mode === "PAPER") {
    const hint = orderFlowPaperHint(data);
    return {
      headline: "Flow confirmation for simulation",
      summary: `Last bar delta ${last?.delta ?? "UNKNOWN"}; CVD ${cvd}.`,
      decisionHint: hint,
      sections: paperDecisionSections(
        hint,
        [
          hint === "supports"
            ? "Signed volume leans with a long-leaning simulated thesis."
            : hint === "contradicts"
              ? "Signed volume leans against a long-leaning simulated thesis — confirm side before draft."
              : "Flow is flat or ambiguous — do not treat as confirmation.",
          `Quality ${last?.quality ?? data.quality ?? "UNKNOWN"}.`,
          "Cross-check order-book fragility before sizing.",
        ],
        args.instrumentId,
        "order-flow",
      ),
    };
  }

  return {
    headline: "Live order flow observational",
    summary: `Observed CVD ${cvd}; provider ${data.provider_id ?? "UNKNOWN"}.`,
    sections: liveObservationalSections(
      [
        `Ledger ${data.ledger_id ?? "UNKNOWN"}.`,
        `Bar quality ${last?.quality ?? data.quality ?? "UNKNOWN"}.`,
        "Flow is broker-reported — no execution implication.",
      ],
      ["Do not treat CVD as directional intent.", "Degraded bars should reduce operational confidence."],
    ),
    relatedLinks: [{ label: "Live canary", to: "/live-canary" }],
  };
}

function buildOrderBookContent(args: BuildLaneModeContentArgs): LaneModeContent {
  const data = args.data as WorkspaceOrderBookResponse | null | undefined;

  if (args.queryState.phase !== "ready" || !data?.available) {
    return {
      headline: args.mode === "DEMO" ? "Order book replay" : args.mode === "PAPER" ? "Liquidity decision context" : "Live order book observational",
      summary: unavailableSummary(args.queryState, args.mode),
      sections: [],
      relatedLinks: args.mode === "LIVE" ? [{ label: "Live canary", to: "/live-canary" }] : undefined,
    };
  }

  const imbalance = data.latest_imbalance_ratio;
  const fragility = data.latest_liquidity_summary?.fragility_score;
  const bookValid = data.latest_book_state_valid;

  const paperHint: PaperDecisionHint =
    bookValid === false
      ? "contradicts"
      : typeof fragility === "number" && fragility > 0.7
        ? "contradicts"
        : typeof imbalance === "number" && Math.abs(imbalance) > 0.2
          ? "neutral"
          : "supports";

  if (args.mode === "DEMO") {
    return {
      headline: "Depth, imbalance & liquidity behavior",
      summary: `Imbalance ratio ${imbalance ?? "UNKNOWN"}; ${data.snapshot_count ?? 0} snapshots.`,
      sections: demoReplaySections(
        "Order-book fixture",
        [
          "Study how imbalance ratio and OFI evolve across snapshots.",
          fragility != null ? `Fragility score ${fragility} — higher values imply thinner liquidity.` : "Inspect liquidity summary for withdrawal vs replenishment.",
          "Link to order-flow lane to see signed volume confirmation.",
        ],
        ["Replay snapshots may not match live DOM granularity."],
      ),
    };
  }

  if (args.mode === "PAPER") {
    return {
      headline: "Liquidity & slippage for simulation",
      summary: `Book valid: ${bookValid ?? "UNKNOWN"}. Imbalance ${imbalance ?? "UNKNOWN"}.`,
      decisionHint: paperHint,
      sections: paperDecisionSections(
        paperHint,
        [
          bookValid === false ? "Invalid book state — avoid aggressive simulated sizing." : "Book state valid for simulation context.",
          fragility != null ? `Fragility ${fragility} — factor into expected slippage.` : "Review impact summary before drafting size.",
          data.latest_impact_summary?.impact_method
            ? `Impact method: ${data.latest_impact_summary.impact_method}`
            : "Use workspace preview to revalidate risk after draft.",
        ],
        args.instrumentId,
        "order-book",
      ),
    };
  }

  return {
    headline: "Live liquidity observational",
    summary: `Observed imbalance ${imbalance ?? "UNKNOWN"}; snapshots ${data.snapshot_count ?? 0}.`,
    sections: liveObservationalSections(
      [
        `OFI ${data.latest_ofi_value ?? "UNKNOWN"} (${data.latest_ofi_method ?? "method unknown"}).`,
        bookValid === false ? "Book marked invalid — treat depth as degraded." : "Book state reported valid.",
        "Visible liquidity is observational only.",
      ],
      ["DOM may be partial vs full exchange depth.", "Stale snapshots reduce confidence."],
    ),
    relatedLinks: [{ label: "Live canary", to: "/live-canary" }],
  };
}

function buildCatalystContent(args: BuildLaneModeContentArgs): LaneModeContent {
  const data = args.data as WorkspaceCatalystResponse | null | undefined;

  if (args.queryState.phase !== "ready" || !data?.available) {
    return {
      headline: args.mode === "DEMO" ? "Catalyst replay" : args.mode === "PAPER" ? "Catalyst thesis context" : "Live catalyst observational",
      summary: unavailableSummary(args.queryState, args.mode),
      sections: [],
    };
  }

  const eventCount = data.catalyst_count ?? data.catalysts?.length ?? 0;
  const latestLabel = data.latest_headline ?? data.latest_lean ?? "UNKNOWN";

  if (args.mode === "DEMO") {
    return {
      headline: "Catalyst replay & event interpretation",
      summary: `${eventCount} catalyst events; latest ${latestLabel}.`,
      sections: demoReplaySections(
        "Public catalyst bridge",
        [
          "Study timing between catalyst publication and price response in replay.",
          "Sentiment and keyword blocks are interpretive — not trade recommendations.",
          data.disclaimer ?? "Follow disclaimer on evidence cards.",
        ],
        ["Historical catalysts may be stale relative to current narrative."],
      ),
    };
  }

  if (args.mode === "PAPER") {
    const hint: PaperDecisionHint = eventCount > 0 ? "neutral" : "insufficient";
    return {
      headline: "Catalyst timing for simulation",
      summary: `Latest catalyst: ${latestLabel}.`,
      decisionHint: hint,
      sections: paperDecisionSections(
        hint,
        [
          eventCount > 0
            ? `${eventCount} events available — confirm relevance to simulated holding period.`
            : "No catalyst events — thesis cannot rely on this lane.",
          "Factor event time vs your simulation horizon.",
          "Draft carries lane provenance only — not a catalyst-driven side.",
        ],
        args.instrumentId,
        "catalyst",
      ),
    };
  }

  return {
    headline: "Live catalyst observational",
    summary: `Observed catalyst context; latest ${latestLabel}.`,
    sections: liveObservationalSections(
      [
        `${eventCount} events in bridge.`,
        "Do not infer unverified causality from observational catalyst state.",
        data.provider_id ? `Provider ${data.provider_id}.` : "Provenance follows public bridge only.",
      ],
      ["Catalyst bridge is read-only in Live.", "Delayed filings may lag market reaction."],
    ),
    relatedLinks: [{ label: "Live canary", to: "/live-canary" }],
  };
}

function buildOptionsContent(args: BuildLaneModeContentArgs): LaneModeContent {
  const data = args.data as WorkspaceOptionsResponse | null | undefined;

  if (args.queryState.phase !== "ready" || !data?.available) {
    return {
      headline: args.mode === "DEMO" ? "Options replay" : args.mode === "PAPER" ? "Options confirmation context" : "Live options observational",
      summary: unavailableSummary(args.queryState, args.mode),
      sections: [],
    };
  }

  const activities = data.activities ?? [];
  const top = activities[0];
  const hint: PaperDecisionHint =
    top?.confirmation_score != null && top.confirmation_score >= 0.6
      ? "supports"
      : activities.length === 0
        ? "insufficient"
        : "neutral";

  if (args.mode === "DEMO") {
    return {
      headline: "Options activity education",
      summary: `${data.activity_count ?? activities.length} unusual activities in fixture.`,
      sections: demoReplaySections(
        "Options fixture",
        [
          "Inspect vol/skew proxies and confirmation scores on activity rows.",
          top ? `Top activity direction ${top.direction_label ?? "UNKNOWN"}.` : "No activity rows — study empty-state limitations.",
          "Dealer and strategy snapshots are interpretive overlays.",
        ],
        ["Options fixture may not cover full chain."],
      ),
    };
  }

  if (args.mode === "PAPER") {
    return {
      headline: "Options confirmation for simulation",
      summary: top
        ? `Lead activity ${top.option_type ?? "UNKNOWN"} ${top.strike ?? ""} · score ${top.confirmation_score ?? "N/A"}`
        : "No unusual activity rows.",
      decisionHint: hint,
      sections: paperDecisionSections(
        hint,
        [
          top?.liquidity_ok === false ? "Liquidity flags failed — size conservatively in simulation." : "Review liquidity flags on lead activity.",
          data.opportunity_snapshot ? "Opportunity fusion snapshot available — cross-check with squeeze lane." : "Cross-check with underlying thesis lanes.",
          "Draft does not infer option structure — confirm equity side manually.",
        ],
        args.instrumentId,
        "options",
      ),
    };
  }

  return {
    headline: "Live options observational",
    summary: `${activities.length} observed activities; chain ${data.chain_available ? "available" : "partial"}.`,
    sections: liveObservationalSections(
      [
        `Provider ${data.provider_id ?? "UNKNOWN"}.`,
        "Observed flow is not directional intent.",
        top ? `Latest direction label ${top.direction_label ?? "UNKNOWN"}.` : "No recent activity rows.",
      ],
      ["No options execution on this lane.", "IV and skew may be delayed."],
    ),
    relatedLinks: [{ label: "Live canary", to: "/live-canary" }],
  };
}

function buildFuturesContent(args: BuildLaneModeContentArgs): LaneModeContent {
  const data = args.data as WorkspaceFuturesResponse | null | undefined;

  if (args.queryState.phase !== "ready" || !data?.available) {
    return {
      headline: args.mode === "DEMO" ? "Futures replay" : args.mode === "PAPER" ? "Macro backdrop for simulation" : "Live futures observational",
      summary: unavailableSummary(args.queryState, args.mode),
      sections: [],
    };
  }

  const snapshots = data.snapshots ?? [];
  const last = snapshots[snapshots.length - 1];
  const signal = data.latest_imbalance_signal ?? last?.imbalance_signal ?? "UNKNOWN";

  if (args.mode === "DEMO") {
    return {
      headline: "Macro & futures interpretation",
      summary: `ES depth snapshots: ${snapshots.length}. Signal ${signal}.`,
      sections: demoReplaySections(
        "Futures fixture",
        [
          "Interpret ES imbalance as macro backdrop — not CFTC positioning.",
          last?.session_state ? `Session ${last.session_state}.` : "Review session state on snapshot rows.",
          "Cross-link to fund/ETF lane for proxy flows.",
        ],
        ["Fixture depth is not live CFTC commitment of traders."],
      ),
    };
  }

  if (args.mode === "PAPER") {
    return {
      headline: "Macro regime for simulated decisions",
      summary: `Backdrop signal ${signal}; fragility ${last?.fragility_score ?? "UNKNOWN"}.`,
      decisionHint: signal === "BUY" || signal === "BID" ? "supports" : signal === "SELL" || signal === "ASK" ? "contradicts" : "neutral",
      sections: paperDecisionSections(
        signal === "BUY" || signal === "BID" ? "supports" : signal === "SELL" || signal === "ASK" ? "contradicts" : "neutral",
        [
          "Factor ES imbalance into equity simulation thesis.",
          last?.rth === false ? "Outside RTH — macro context may be thin." : "RTH snapshot available.",
          "Draft on equity lane — futures context is backdrop only.",
        ],
        args.instrumentId,
        "futures",
      ),
    };
  }

  return {
    headline: "Live futures observational",
    summary: `Observed ES context; signal ${signal}.`,
    sections: liveObservationalSections(
      [
        `Exchange ${last?.exchange ?? "UNKNOWN"}.`,
        "Observational depth — no execution controls.",
        last?.epistemic_class ? `Epistemic ${last.epistemic_class}.` : "Treat as macro backdrop only.",
      ],
      ["Not live CFTC positioning.", "Futures lane does not authorize trades."],
    ),
    relatedLinks: [{ label: "Live canary", to: "/live-canary" }],
  };
}

function buildLargeTransactionsContent(args: BuildLaneModeContentArgs): LaneModeContent {
  const data = args.data as WorkspaceLargeTransactionsResponse | null | undefined;

  if (args.queryState.phase !== "ready" || !data?.available) {
    return {
      headline: args.mode === "DEMO" ? "Large print interpretation" : args.mode === "PAPER" ? "Print thesis context" : "Live prints observational",
      summary: unavailableSummary(args.queryState, args.mode),
      sections: [],
    };
  }

  const prints = data.prints ?? [];
  const last = prints[prints.length - 1];

  if (args.mode === "DEMO") {
    return {
      headline: "Size print interpretation",
      summary: `${data.print_count ?? prints.length} prints in fixture.`,
      sections: demoReplaySections(
        "Large-print fixture",
        [
          last ? `Latest print size ${last.print_size ?? "UNKNOWN"} · side label ${last.side ?? "UNKNOWN"}.` : "Inspect print table for threshold gates.",
          "Aggressor provenance remains explicit on each row.",
          "Prints show size — not verified directional intent.",
        ],
        ["Historical prints may not repeat in live tape."],
      ),
    };
  }

  if (args.mode === "PAPER") {
    const hint: PaperDecisionHint =
      last?.direction_label === "BUY" || last?.side === "BUY"
        ? "supports"
        : last?.direction_label === "SELL" || last?.side === "SELL"
          ? "contradicts"
          : prints.length > 0
            ? "neutral"
            : "insufficient";
    return {
      headline: "Prints vs simulated thesis",
      summary: last ? `Latest print ${last.print_size ?? "?"} @ ${last.price ?? "?"}` : "No prints available.",
      decisionHint: hint,
      sections: paperDecisionSections(
        hint,
        [
          last?.threshold_gate_ok === false ? "Threshold gate failed — lower confidence." : "Threshold gate passed on latest print.",
          "Confirm whether print timing supports holding period.",
          "Do not infer intent from size alone.",
        ],
        args.instrumentId,
        "large-transactions",
      ),
    };
  }

  return {
    headline: "Live large prints observational",
    summary: `${prints.length} observed prints.`,
    sections: liveObservationalSections(
      [
        "Prints are observational — aggressor unknown unless stated.",
        last ? `Latest epistemic ${last.epistemic_class ?? "UNKNOWN"}.` : "No recent prints.",
        "Do not treat prints as verified directional intent.",
      ],
      ["Size alone is not a trade signal.", "Tape may be partial vs full venue."],
    ),
    relatedLinks: [{ label: "Live canary", to: "/live-canary" }],
  };
}

function buildDisclosureContent(args: BuildLaneModeContentArgs): LaneModeContent {
  const data = args.data as WorkspaceDisclosureResponse | null | undefined;

  if (args.queryState.phase !== "ready" || !data?.available) {
    return {
      headline: args.mode === "DEMO" ? "Filing interpretation" : args.mode === "PAPER" ? "Disclosure thesis context" : "Live filings observational",
      summary: unavailableSummary(args.queryState, args.mode),
      sections: [],
    };
  }

  const events = data.events ?? [];
  const latest = events[0];

  if (args.mode === "DEMO") {
    return {
      headline: "Filing & event interpretation",
      summary: `${data.event_count ?? events.length} disclosure events.`,
      sections: demoReplaySections(
        "Disclosure fixture",
        [
          latest ? `Latest form ${latest.form_type ?? "UNKNOWN"} · ${latest.accepted_at ?? latest.transaction_date ?? "time unknown"}.` : "Study empty filing state.",
          "Interpret sentiment blocks as research aids — not recommendations.",
          "Check publication state and provenance on each event.",
        ],
        ["Filings may be delayed vs market reaction."],
      ),
    };
  }

  if (args.mode === "PAPER") {
    return {
      headline: "Disclosure evidence for simulation",
      summary: latest ? `Latest ${latest.form_type ?? "filing"} relevant to thesis review.` : "No filing events.",
      decisionHint: events.length > 0 ? "neutral" : "insufficient",
      sections: paperDecisionSections(
        events.length > 0 ? "neutral" : "insufficient",
        [
          events.length > 0 ? "Confirm materiality before drafting." : "Cannot rely on disclosure lane without events.",
          "Draft provenance records lane — not filing-driven side.",
          "Re-preview after portfolio state changes.",
        ],
        args.instrumentId,
        "disclosure",
      ),
    };
  }

  return {
    headline: "Live filings observational",
    summary: `${events.length} read-only filing events.`,
    sections: liveObservationalSections(
      [
        latest ? `Latest accepted ${latest.accepted_at ?? latest.transaction_date ?? "UNKNOWN"}.` : "No filings loaded.",
        "Delayed filings remain read-only.",
        data.provider_id ? `Provider ${data.provider_id}.` : "Provenance follows filing bridge.",
      ],
      ["Filings do not authorize trades.", "Stale filings reduce operational confidence."],
    ),
    relatedLinks: [{ label: "Live canary", to: "/live-canary" }],
  };
}

function buildInstitutionalFlowContent(args: BuildLaneModeContentArgs): LaneModeContent {
  const data = args.data as WorkspaceInstitutionalFlowResponse | null | undefined;
  const families = data?.families ?? [];
  const availableFamilies = families.filter((row) => row.available);
  const hasEvidence = availableFamilies.length > 0;

  if (args.queryState.phase !== "ready" || !hasEvidence) {
    return {
      headline: args.mode === "DEMO" ? "Whale flow doctrine" : args.mode === "PAPER" ? "Institutional thesis context" : "Live institutional observational",
      summary: unavailableSummary(args.queryState, args.mode),
      sections: [],
    };
  }

  const lead = availableFamilies[0];

  if (args.mode === "DEMO") {
    return {
      headline: "Institutional flow education",
      summary: `${data!.available_family_count}/${data!.family_count} entitled families available.`,
      sections: demoReplaySections(
        "Institutional fixture",
        [
          lead ? `Example family ${lead.label} on ${lead.entitled_symbol}.` : "Review family grid for doctrine notes.",
          "Whale flow shows participation — not verified intent.",
          "Cross-check with order-flow CVD where available.",
        ],
        ["Historical whale labels may not transfer to live tape."],
      ),
    };
  }

  if (args.mode === "PAPER") {
    const hint: PaperDecisionHint = availableFamilies.length >= 2 ? "neutral" : "insufficient";
    return {
      headline: "Institutional confirmation for simulation",
      summary: `${availableFamilies.length} entitled families for ${args.instrumentId}.`,
      decisionHint: hint,
      sections: paperDecisionSections(
        hint,
        [
          "Treat family availability as thesis context — not execution authority.",
          "Aggressor remains unknown unless explicitly labeled on donor bridge.",
          "Draft side defaults to BUY × 1 — confirm manually.",
        ],
        args.instrumentId,
        "institutional-flow",
      ),
    };
  }

  return {
    headline: "Live institutional flow observational",
    summary: `${availableFamilies.length} broker-observed families.`,
    sections: liveObservationalSections(
      [
        "Institutional flow is observational.",
        data?.epistemic_class ? `Epistemic ${data.epistemic_class}.` : "Do not infer verified intent.",
        lead ? `Lead family ${lead.label}.` : "No entitled families.",
      ],
      ["Flow labels are not trade signals.", "Provider degradation reduces confidence."],
    ),
    relatedLinks: [{ label: "Live canary", to: "/live-canary" }],
  };
}

function buildFundEtfContent(args: BuildLaneModeContentArgs): LaneModeContent {
  const data = args.data as WorkspaceFundEtfResponse | null | undefined;

  if (args.queryState.phase !== "ready" || !data?.available) {
    return {
      headline: args.mode === "DEMO" ? "Fund flow education" : args.mode === "PAPER" ? "ETF proxy for simulation" : "Live fund flow observational",
      summary: unavailableSummary(args.queryState, args.mode),
      sections: [],
    };
  }

  const events = data.events ?? [];
  const latest = events[0];

  if (args.mode === "DEMO") {
    return {
      headline: "ETF & fund-flow proxy education",
      summary: `${data.event_count ?? events.length} proxy events.`,
      sections: demoReplaySections(
        "Fund/ETF fixture",
        [
          latest ? `Latest proxy ${latest.etf_ticker ?? latest.regime_label ?? "UNKNOWN"}.` : "Study proxy limitations on empty state.",
          "Fund flows are cross-asset context for equity thesis.",
          "Link to futures lane for macro backdrop.",
        ],
        ["Proxies are not direct equity order flow."],
      ),
    };
  }

  if (args.mode === "PAPER") {
    return {
      headline: "ETF proxy for simulated position reasoning",
      summary: latest ? `Proxy ${latest.etf_ticker ?? latest.regime_label ?? "event"} available.` : "No proxy events.",
      decisionHint: events.length > 0 ? "neutral" : "insufficient",
      sections: paperDecisionSections(
        events.length > 0 ? "neutral" : "insufficient",
        [
          "Use proxy flow as supporting context — not primary trigger.",
          "Confirm symbol match between proxy and workspace instrument.",
          "Re-preview ticket after portfolio updates.",
        ],
        args.instrumentId,
        "fund-etf",
      ),
    };
  }

  return {
    headline: "Live fund-flow observational",
    summary: `${events.length} observational proxy events.`,
    sections: liveObservationalSections(
      [
        latest ? `Latest flow direction ${latest.flow_direction ?? "UNKNOWN"}.` : "No proxy events loaded.",
        "Fund-flow proxies are observational.",
        data.provider_id ? `Provider ${data.provider_id}.` : "Provenance follows proxy bridge.",
      ],
      ["Proxies may lag primary equity tape.", "No execution on this lane."],
    ),
    relatedLinks: [{ label: "Live canary", to: "/live-canary" }],
  };
}

const BUILDERS: Record<WorkspaceLaneModuleId, (args: BuildLaneModeContentArgs) => LaneModeContent> = {
  squeeze: buildSqueezeContent,
  "order-flow": buildOrderFlowContent,
  "order-book": buildOrderBookContent,
  catalyst: buildCatalystContent,
  options: buildOptionsContent,
  futures: buildFuturesContent,
  "large-transactions": buildLargeTransactionsContent,
  disclosure: buildDisclosureContent,
  "institutional-flow": buildInstitutionalFlowContent,
  "fund-etf": buildFundEtfContent,
};

export function buildLaneModeContent(args: BuildLaneModeContentArgs): LaneModeContent {
  return BUILDERS[args.moduleId](args);
}

export function laneModuleTitle(moduleId: WorkspaceModuleId): string {
  if (moduleId === "overview") return "Overview";
  const titles: Record<WorkspaceLaneModuleId, string> = {
    squeeze: "Short Squeeze",
    "order-flow": "Order Flow",
    "order-book": "Order Book",
    catalyst: "Catalyst",
    options: "Options",
    futures: "Futures",
    "large-transactions": "Large Transactions",
    disclosure: "Disclosure",
    "institutional-flow": "Institutional Flow",
    "fund-etf": "Fund / ETF",
  };
  return titles[moduleId];
}
