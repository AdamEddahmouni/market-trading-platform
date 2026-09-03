"""Research pipeline summary — offline / historical, not live trading."""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from dashboard.components.empty import empty_state, missing_file
from dashboard.data import paths as P
from dashboard.data.loaders import load_json


def render(settings: Dict[str, Any]) -> None:
    del settings
    st.markdown(
        "<div class='research-banner'><strong>Historical research only</strong> — "
        "IVolatility / pattern miner outputs under <code>state/learning/</code>. "
        "Does not place trades and is independent of the live agent.</div>",
        unsafe_allow_html=True,
    )

    miner = load_json(P.MINER_RESULT_PATH, {})
    proposals = load_json(P.PROPOSALS_PATH, {})

    if not miner["ok"]:
        missing_file("state/learning/spy_qqq_miner_result.json")
    else:
        data = miner["data"] if isinstance(miner.get("data"), dict) else {}
        discovery = data.get("discovery_patterns_passing_n") or []
        survivors = data.get("survivors") or []
        found_nr = data.get("found_but_did_not_replicate") or []
        min_n = data.get("min_n", 30)
        n_disc = len(discovery) if isinstance(discovery, list) else int(discovery or 0)
        n_surv = len(survivors) if isinstance(survivors, list) else int(survivors or 0)
        headline = (
            f"{n_disc} discovery patterns (N≥{min_n}), "
            f"{n_surv} survived out-of-sample validation"
        )
        st.subheader(headline)
        c1, c2, c3 = st.columns(3)
        c1.metric("Discovery patterns", n_disc)
        c2.metric("OOS survivors", n_surv)
        c3.metric("Found but did not replicate", len(found_nr) if isinstance(found_nr, list) else 0)
        if data.get("path_a_note"):
            st.info(str(data.get("path_a_note")))
        if data.get("tod_limitation_note"):
            st.caption(str(data.get("tod_limitation_note")))
        if isinstance(survivors, list) and survivors:
            st.markdown("**Survivors**")
            st.dataframe(pd.DataFrame(survivors), use_container_width=True, hide_index=True)
        elif n_surv == 0:
            st.warning("0 patterns survived chronological out-of-sample validation — no obvious mined edge in this panel.")

    st.subheader("Latest proposals")
    if not proposals["ok"]:
        missing_file("state/learning/proposals/latest_proposal.json")
    else:
        pdata = proposals["data"] if isinstance(proposals.get("data"), dict) else {}
        st.caption(f"generated_at={pdata.get('generated_at')}")
        props = pdata.get("proposals") or []
        if isinstance(props, list) and props:
            st.dataframe(pd.DataFrame(props), use_container_width=True, hide_index=True)
        else:
            empty_state("No proposals in latest_proposal.json")
