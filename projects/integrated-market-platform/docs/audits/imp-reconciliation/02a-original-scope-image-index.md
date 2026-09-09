# 02a — Tier A Image Evidence Index

Status: **COMPLETE (WS02)**. Source directory:
`C:\Users\adame\Desktop\market-trading-platform\project-scope-images\`
(7 PNG files). Method: local Windows.Media.Ocr (en-US) extraction, 2026-09-06;
transcripts in `.freebuff/ocr-output/IMG-*.txt` (gitignored scratch).

Note on OCR: quoted text is normalized from OCR output; obviously garbled
characters are marked `[sic]`. "Leve12" / "1B" / "1 2" in subjects read as
"Level2" / "IB" / "L2".

## Inventory

| Image ID | Filename | Apparent sequence | Readable? | Major topic | Requirements present | Continues another image? | Confidence | Notes |
|---|---|---|---|---|---|---|---|---|
| IMG-001 | Codex Image Sep 6, 2026, 09_20_40 PM.png | Earliest captured (search view over 7/18–7/28) | Yes | Outlook search: "FUTURE + CVD" thread open; sidebar shows Short Interest Formula, Screener Project, CVD & Level 2, Change in Availability | Yes — Future+CVD use IB API; enhanced codeset coming; screener/short-interest threads exist | No (folder/search context) | CONFIRMED (high-text OCR) | Verbatim: "Both use Interactive Brokers API."; Kaltura media links for Future+CVD; Adam reply "Sounds good, thank you" 7/27 4:36 PM |
| IMG-002 | Codex Image Sep 6, 2026, 09_20_51 PM.png | 2026-07-27→07-28 | Yes | Email: "CVD & Level 2 Project Full Code from Hyuntae Jeong (John)" + professor forward to Adam | Yes — CVD/Level2 donor code supplied; README/USAGE docs | No | CONFIRMED | Hyuntae Jeong `<hzj5293@psu.edu>` 7/27 9:35 PM; repo `github.com/RumiaKitinari/tradingCVDBubble`; attachments `tradingCVDBubble-main.zip`, README.pdf (213 KB), USAGE.pdf (722 KB); professor forwarded 7/28 7:35 AM |
| IMG-003 | Codex Image Sep 6, 2026, 09_20_56 PM.png | 2026-07-31→08-01 | Yes | Email: "Option Project" — Eric Strzalkowski repo + professor forward to Adam | Yes — Options donor supplied; paid APIs NOT used (trials); profitability disclaimer | No | CONFIRMED | Eric Strzalkowski `<eks5832@psu.edu>` 7/31 10:34 PM; verbatim: "I don't have any of the paid api keys like unusual whales and ivolatil[e]... making new accounts with trials"; "The project isn't reliably making money yet but it is almost there with the logic" |
| IMG-004 | Codex Image Sep 6, 2026, 09_21_03 PM.png | 2026-06-06 → 08-01 | Yes | Email: "CVD Project (Eric's Materials)" — professor to CVD group, forwarded to Adam | Yes — Eric_futuresX supplied as CVD/Future material to the CVD group | No | CONFIRMED | Professor to Zheng, Jason & Jeong, Hyuntae 6/6/2026 12:32 PM; Kaltura media links; attachment `Eric_futuresX-main.zip` (852 KB) forwarded to Adam 8/1 7:48 AM. Establishes SRC-005 authorization within the CVD/Future stream |
| IMG-005 | Codex Image Sep 6, 2026, 09_21_09 PM.png | 2026-08-01 7:49 AM | Yes | **Central professor scope message: "CVD/Leve12/Option/Future"** | Yes — the integrated-platform mandate + IB data requirements | No | CONFIRMED | Verbatim quotes preserved in 02-scope-authority-ledger.md F-series. Offers to pay one month of IB data; "For option, you maybe able to use IB as well"; "For Future, Eric's using IB data"; "integrated platform where your short squeeze, your CVD/Level2 and Options/Future come together nicely" |
| IMG-006 | Codex Image Sep 6, 2026, 09_21_33 PM.png | 2026-08-25 → 09-06 | Yes | Email: "Link" — professor: "This is Future Project." + Lucas Bichara "Claude Code News" OneDrive share | Yes — Claude Code News = Future Project; sidebar shows the Heller correction email ("Future Project — Hello Adam: This was not...") | No | CONFIRMED | Professor 9/6/2026 7:27→7:40 PM to Eric Feng + Adam; Bichara, Lucas `<ljb6293@psu.edu>` 7:40/7:50/7:57 PM; OneDrive link `pennstateoffice365-my.sharepoint.com/personal/ljb6293_psu.edu/.../Claude Code News`. Correction email subject visible dated ~8/28 |
| IMG-007 | Codex Image Sep 6, 2026, 09_21_41 PM.png | 2026-09-06 (current) | Partial | Desktop context: Freebuff/Cursor chat (Adam preparing the reconstruction program) + OneDrive "Claude Code News" folder + workspace file listing | Implied — Adam's reconstruction intent ("construct the original IMP... I will also provide [what the pro]fessor added on later") | No | MODERATE (partial text; mixed UI) | Confirms the current reconciliation program is Adam's own initiative; workspace layout matches this repo; OneDrive folder "Claude Code News" under Lucas Bichara's Penn State account |

## Original-scope markers visible in the image set

- **Earliest dated thread:** "Short Interest Formula" (7/24/2026) and "Screener
  Project" (7/27/2026) — original short-squeeze screener stream (IMG-001).
- **Project streams documented:** Short Squeeze screener, CVD & Level 2
  (Hyuntae Jeong), Options (Eric Strzalkowski), Future (Eric_futuresX then
  Claude Code News), all under professor direction.
- **Explicitly NOT in this image set:** the full original proposal document /
  initial project-goal screenshots. Original scope is therefore reconstructed
  from the earliest email subjects plus the 8/1 integrated-platform message,
  at MODERATE confidence, and any later-supplied proposal screenshots take
  precedence (see 14-open-decisions M1-closed note).

## Requirements extracted from images (leading to ORG-* / LATER-* IDs)

| Image | Requirement evidence | Assigned ID | Confidence |
|---|---|---|---|
| IMG-001 | Short Interest Formula thread; Screener Project thread — short-squeeze screener is the original stream | ORG-001 (see ledger) | MODERATE (subjects only) |
| IMG-001 | Future + CVD: "Both use Interactive Brokers API."; "An enhanced codeset will be coming your way shortly." | LATER-003 (Futures+CVD stream; IB data) | CONFIRMED |
| IMG-002 | CVD/Level2 full code + README/USAGE from Hyuntae Jeong | LATER-001/002 (CVD donor) | CONFIRMED |
| IMG-003 | Options project repo; trial-based providers; unprofitable disclaimer | LATER-004 (Options donor) | CONFIRMED |
| IMG-004 | Eric_futuresX supplied to CVD group as "CVD Project (Eric's Materials)" | LATER-003/005 (futures donor) | CONFIRMED |
| IMG-005 | Integrated platform mandate; CVD L1+L2 IB required; IB for options maybe; Future on IB data | LATER-006..011 | CONFIRMED |
| IMG-006 | "This is Future Project." — Claude Code News (Bichara) | LATER-012 | CONFIRMED |
| IMG-006 | "Future Project — Hello Adam: This was not..." (Heller correction) | Correction evidence | CONFIRMED (subject visible) |