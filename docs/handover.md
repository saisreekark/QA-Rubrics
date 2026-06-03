# Handover — QA Rubrics project (Apr 29, 2026)

> A follow-up Connect on **2026-05-14** resolved most of the open items
> from this call and added new framework changes. See
> `docs/connect-2026-05-14.md` for the diff.
>
> For the keyboard-level execution sequence — phase by phase, with
> tickable checkboxes — see `docs/execution-plan.md`.

## Call summary

Pooja Talwar and Zaidul Mukhtar handed the QA Rubrics project to the new
engineering pod (Sai Sreekar Kanaparthy, Tarun Dixit, Laxmi Vivek Salveru,
Zaidul Mukhtar, Battula Kumar, Karthik Maila) on **Apr 29, 2026**.

The pitch in one sentence: today, QAs audit ~15% of closed cases by hand
against a fixed rubric; this project replaces that with a daily Gemini batch
job that audits **100% of cases** and emits per-case Root Cause Analysis
across six audit frameworks.

The pipeline is **already in production** — the daily Vertex Colab schedule
(`rubrics-automation-run`) has 63 successful runs. The unsolved problem is
**accuracy**: the bot is at ~50% and needs ~80% to be demo-able.

## Decisions taken on the call

1. **Stay on Google Sheets ("Tricks") for now.** Tricks may become
   non-compliant, but no formal Google notice has landed. We don't preempt.
   Pooja is in parallel scoping a BigQuery migration as the fallback.
2. **Focus is purely on prompt accuracy.** The schedulers, dashboard, data
   ingestion, and L3 scoring are wired up. Don't refactor them.
3. **Validation stays human-in-the-loop for now**, but Sai's LLM-as-judge
   idea (Gemini scoring Gemini's outputs against historical QA corrections)
   is on the table to remove that bottleneck.
4. **Test in small batches** (Zaidul): generate outputs for 100–200 cases at
   a time, hit >90% on the small set, then scale to ~3000.

## Action items

| # | Owner | Item |
|---|---|---|
| 1 | The group | Read the Pantheon notebook code; map the schedulers (we expect 3 — input pull, code run, output export — but only 1 is visible to us). |
| 2 | Zaidul | Send the **updated categorization framework** with the new L3 driver under "Process Gap". |
| 3 | Zaidul | Update the Tricks sheet with the latest RCA framework changes. |
| 4 | Pooja | Raise the Tricks non-compliance issue with the client; plan a data-migration alternative. |
| 5 | Pooja | Plan the proactive migration from Tricks → BigQuery. |
| 6 | The group | Process all project documentation; come back with follow-up items. |
| 7 | Sai Sreekar | Set up clarification calls next week; establish a week-long cadence with key stakeholders. |

## Deadline pressure (from Pooja)

- **Demo to client**: 3rd week of next month → roughly **June 15–21, 2026**.
  Confirm the exact date with Pooja.
- **Full release**: **July 2026**. "Cannot delay more than July."
- Wrap up Pooja's April deliverables first, then move into "full throttle
  mode" on Rubrics.

## Stakeholder access

Zaidul: "Block my calendar anytime between 2 and 12, apart from internal /
client calls." Pooja: "Feel free to set up any clarification calls next week
or schedule a week-long cadence."
