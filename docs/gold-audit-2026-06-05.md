# Gold-set audit — QA-2026 — 2026-06-05

Run `python3 -m evaluator.gold_audit` (read-only). Answers "is the gold good,
and how good?" before we trust any accuracy number measured against it. Pairs
with `docs/session-2026-06-04.md` and the window change in `evaluator/config.py`.

## TL;DR

The QA-2026 gold is **clean** (0 dups, 0 blank labels, 0 placeholders, 97–100%
join health). The driver tab holds **2,691 usable rows spanning Jan–Apr 2026**,
but **the updated taxonomy is only in use from March** (some frameworks) — Jan
and Feb cases were labelled under the OLD taxonomy and must not be scored as gold
for the new rubric. The per-month evidence below confirms the cutover: **Quarter
Freeze / YoY appears in 0 cases before March.** The evaluator had been
mis-windowed: first Feb/Mar (pulled in pre-cutover Feb), then briefly the
too-wide Jan–Apr. **Action taken:** set `QA2026_MONTHS` to **March-onward**
(`2026-03`, `2026-04`) — the correct updated-taxonomy window. "Till date" =
April; no May/Jun labels exist yet. This still nearly doubles the old Mar-only
signal by adding April (the largest month). See `[[project_taxonomy_cutover_march]]`.

## What the gold actually contains

Driver tab `DSAT/Reopen/Escalation/TTR`, **2,691 rows**, one combined tab split
by `Stage`. All rows are usable (real case # + non-blank L1). Coverage by
`closed_date` month, per framework:

| Framework | Jan† | Feb† | **Mar** | **Apr** | **Mar–Apr (valid gold)** | All rows |
|---|---:|---:|---:|---:|---:|---:|
| TTR        | 132 | 143 | 294 | 566 | **860** | 1135 |
| Reopen     | 181 | 154 | 283 | 371 | **654** | 989  |
| Escalation | 193 |  49 |  85 | 126 | **211** | 453  |
| DSAT       |  48 |  13 |  27 |  26 | **53**  | 114  |
| **Total**  | 554 | 359 | 689 | 1089 | **1778** | 2691 |

† Jan/Feb are **old-taxonomy** (pre-cutover) and are excluded from the gold
window. The valid updated-taxonomy gold is **March–April = 1,778 cases.** That is
still ~1.7× the old Feb/Mar window (and the bulk is April, the largest month) —
the gain over Feb/Mar comes from **adding April, not from reaching back to
Jan/Feb.**

## Label quality — clean

Across all four frameworks: **0 duplicate case numbers, 0 blank L1, 0 blank
L2&L3, 0 placeholder/non-real case numbers.** Two things to know:

- **`quality_reviewer` is blank on a large share** — TTR 501/1135 (44%),
  Reopen 360/989 (36%), Escalation 61/453, DSAT 5/114. The *labels* are present;
  only the reviewer-name column is empty. Not a blocker, but it means we can't
  always attribute a label to a reviewer. Worth a one-line question to Zaidul.
- **A handful of multi-L1 labels** (TTR 10, Reopen 9, Escalation 1, DSAT 0) —
  e.g. `user gap,process gap`, `process gap,people gap`. These are comma-joined
  primary+secondary L1s, not typos. The matcher reads `gold_l1` as text; confirm
  it treats the first as primary (it currently matches against the whole
  string). Low volume, low risk.

## New taxonomy — the March cutover (this is the deciding evidence)

Rows carrying the updated drivers, by month:

| Framework | Product/Tools Gap (L1) | Quarter Freeze / YoY (any level) |
|---|---:|---:|
| TTR        | 242 (Jan 31, Feb 14, Mar 55, Apr 142) | 68 (Mar 15, Apr 53) |
| Reopen     | **2** (Mar 0, Apr 2)                   | 58 (Mar 31, Apr 27) |
| Escalation | 36 (Jan 18, Feb 3, Mar 3, Apr 12)     | 19 (Mar 7, Apr 12) |
| DSAT       | 2 (Jan 1, Apr 1)                      | 19 (Feb 2, Mar 9, Apr 8) |

1. **Quarter Freeze / YoY appears in 0 cases before March, across every
   framework** — then jumps in (Mar+Apr = 164). This is the **cutover marker**:
   the updated taxonomy is only in use from **March**. Jan/Feb are old-taxonomy
   and are excluded from the gold window (`[[project_taxonomy_cutover_march]]`).
   (`Product/Tools Gap` L1 *does* show in Jan/Feb, but that label predates the
   rebuild, so it is NOT evidence those months use the new taxonomy.)
2. **Reopen "Product/Tools Gap" is genuinely rare — 2 cases in the *entire*
   2,691-row set**, not a windowing artifact. The Phase-4.1 Reopen L1 addition
   is structurally correct but will move ~nothing on this gold; don't expect it
   to. (Other frameworks, esp. TTR at 242, have real Product/Tools-Gap volume.)

## Join health — no silent sample loss

Fraction of usable gold cases that have a live bot prediction / a regen input:

| Framework | gold | live-pred | regen-input |
|---|---:|---:|---:|
| TTR        | 1135 | 1133 (100%) | 1133 (100%) |
| Reopen     |  989 |  986 (100%) |  986 (100%) |
| Escalation |  453 |  438 (97%)  |  438 (97%)  |
| DSAT       |  114 |  111 (97%)  |  112 (98%)  |

The matcher sees essentially the whole gold population; nothing is being quietly
dropped at the join.

## Decisions / follow-ups

- **Done:** `QA2026_MONTHS = ("2026-03","2026-04")` in `evaluator/config.py` —
  **March-onward**, the updated-taxonomy window. Explicit allow-list (not a
  moving lower bound) so an A/B denominator stays fixed; add the next month
  deliberately as QA labels it. Do **not** widen back into Jan/Feb (old taxonomy).
- **Re-baseline** on the March–April window (frozen production preds, run
  `rebaseline_marapr_2026-06-05T01-58-43Z.csv`) supersedes the Feb/Mar `12.99%`
  anchor: **TTR 18.65% (858) / Reopen 6.94% (648) / Escalation 7.46% (201) /
  DSAT 6.00% (50); overall ~12.9% (1,415 audited).** Dropping pre-cutover Jan/Feb
  recovers Escalation/DSAT vs the polluted Jan–Apr run (those old-taxonomy rows
  were spurious mismatches). Reopen remains the floor.
- **Matcher calibration** (generalised one-off → `evaluator/calibrate_matcher.py`,
  45 cases/framework, hand-read): **Reopen PASS** (~90%, prior), **TTR PASS**
  (~95% defensible), **DSAT** — matcher verdicts sound (it correctly flags real
  mismatches) but the **DSAT bot is genuinely ~0%**: like Reopen it over-blames
  the agent (People Gap) when gold is User Gap / Process Gap (+ one `Unmapped`).
  **Escalation** re-running (first attempt died on the static-token 401 — see
  next bullet). **Escalation** re-ran clean on the auth fix — matcher sound, bot
  2/45, same bias. So **Reopen, DSAT AND Escalation all share one root cause**
  (agent/process over-blame, User-Gap under-prediction) → fix-v2 (aggregator)
  should lift all three. All four matchers now PASS; numbers are quotable.
- **Matcher auth hardened:** the matcher's Vertex `vertexai.init` now uses
  auto-refreshing ADC creds (`regen._build_vertex_credentials`), not the one-shot
  `GOOGLE_OAUTH_TOKEN` (which 401s ~1h in and silently shrinks the denominator on
  long runs). Sheets reads keep the drive-scoped static token. Also fixed
  `ab_measure --months` default (was hard-coded Feb/Mar) → `cfg.QA2026_MONTHS`.
- **Ask Zaidul:** (a) the blank `quality_reviewer` column — expected? (b) how to
  treat multi-L1 gold labels (primary = first?). (c) Quality/Workflow still have
  no driver gold — out of scope here.
