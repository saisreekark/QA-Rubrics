# Resources

Every link, ID, and stakeholder used by this project.

## Sheets, Docs, BRDs

| Resource | Link / ID |
|---|---|
| **I/O sheet (Tricks)** — input `Cases for Summary`, output `RCA_Analysis_Output_1` | https://docs.google.com/spreadsheets/d/1Lmo5laSelj8Yp-ANjuZ_cQVnVM3W9XB6mNRt_J94juM/edit |
| **Voice of Seller RCA Frameworks** (authoritative L1/L2/L3 — includes the confirmed driver updates) | `1VXtXkbY9PkX2_7RODj2kco3SYSMzYpXyOMt1CPZfZ9Q` — one tab per framework: `TTR Root Cause Analysis` (gid 0), `ReOpen Cases Root Cause Analysis` (929537954), `DSAT Root Cause Analysis` (347015126), `Escalations Root Cause Analysis` (1070001996), `Quality` (877315225), `Workflow Adherence & Compliance Audits` (1793285379). Layout: col A = Level 1, B = Level 2, C = Level 3, D = Definitions/Examples. |
| **Q+ summary / AI Drivers** | https://docs.google.com/document/d/1l5_uW4z-t_H_KdsGPV_88xiIsBd4W_qka1lS8dA2YHs/edit |
| SOP_Guide | `1LJPbOEi7eUB21ndEFx8NFLc3QRBxjF_lVf1lusRIvkw` |
| Terms_Conditions | `14uSCmn0OZB9x3Mm2Zi6HsrVI5I181mpx_ESlA2kQmak` |
| Plan_Summary | `1A3lwFGFAmiNHCTsKg2lNhn74eC0tRGYg6vaPzdyUr9g` |
| Do_Not_Contact_Data | `1J0VyGVmWjoZBbyk7Ra9vl2Bh3mdG6ZCMADkCzBhUh6Y` (tab: `Do NOT tag`) |

## Newly shared (2026-05-14 Connect)

| Doc | ID | Purpose |
|---|---|---|
| Rubrics — Root Cause Analysis — Feasibility | `1zLLRxoBbFIMWdMy3pB9mVOKHitqOrpEMrqYdj4d5uBc` | Feasibility / approach doc — read first before prompt translation. |
| QA-team prompt review doc | `1ALZRqSB2tqTAYZs_HlfoqN-fDOxyXsA6GDbwPOUWpXc` | Where Zaidul's QA team leaves comments after testing prompts. |
| Additional sheet (RCA labelling) | `1LZ6z_csxzkWB5IARImKyifC81zJmJmqBf_nNKkdaZx4` | Purpose TBC — ask Zaidul in live session. |
| Additional doc | `1W4GtzgvBhnJUghE4h5S7yUmavz8Wm7UDrhE3HpwsSsg` | Purpose TBC. |
| **QA dump — human ground-truth labels** (NOT legacy; see `connect-2026-05-29.md`) | `1tbrQxJbjRLEn6yKB7djXsPfkFMKWHICKTy-X8Y5KzRY` | Per-framework label tabs (`TTR`/`Reopen`/`Escalation`/`DSAT`/`Quality`/`Compliance and Workflow adherence`) with reviewer L1/L2/L3, plus bot predictions in `RCA_Analysis_Output` (header on row 2). The evaluator's label-match gold source. |
| **Legacy** — old I/O sheet 2 | `1G3p6oKcsp71YP1pI180gow1XBn47KpXA1zZQa6ej154` | Commented out in notebook cell 2. |

## Pantheon notebook

- Live URL: https://pantheon.corp.google.com/agent-platform/colab/notebooks?activeNb=projects%2Fgtm-cloud-helpdesk%2Flocations%2Fus-central1%2Frepositories%2F1b4ad4ee-53ba-4541-9492-1dc89d100607&project=gtm-cloud-helpdesk
- Local mirror: `notebook/content.ipynb`
- Display name: `Rubrics_finalpipeline_rh (Jan 29, 2026, 10:52:21 AM)`
- Last contributor: Elavala Srinivasa Reddy (`elreddy@`)

## GCP

| | |
|---|---|
| Project ID | `gtm-cloud-helpdesk` |
| Project number | `653428233292` |
| Region | `us-central1` |
| Dataform repo (notebook host) | `projects/gtm-cloud-helpdesk/locations/us-central1/repositories/1b4ad4ee-53ba-4541-9492-1dc89d100607` |
| Notebook file path in repo | `content.ipynb` |
| Notebook runtime template | `projects/653428233292/locations/us-central1/notebookRuntimeTemplates/1413241877599092736` |
| Scheduler (this pod owns) | `rubrics-automation-run`, id `1105207098007879680`, cron `0 12 * * * Asia/Calcutta` |
| Scheduler executor | `ukirdeankush@google.com` |
| Output bucket | `gs://analytics_genai` |

## Stakeholders

| Person | Role | Contact |
|---|---|---|
| Sai Sreekar Kanaparthy | New eng lead on Rubrics (this pod) | `kanapasai@google.com` |
| Pooja Talwar | Project lead, deadline owner | xWF |
| Zaidul Mukhtar | QA owner, rubric definitions, live-session reviewer | xWF |
| Rishita | Context Caching owner; OAuth-token workaround originator | (TBC) |
| Tarun Dixit | SMB labels, dashboard plumbing, proposed daily sync cadence | xWF |
| Laxmi Vivek Salveru | Pod engineer | xWF |
| Battula Kumar | Pod engineer | xWF |
| Karthik Maila | Pod engineer | `karthikkumar.maila@cognizant.com` |
| Vikram Singh | MIS dashboard owner, data-load schedulers | (intro pending) |
| Elavala Srinivasa Reddy | Last notebook contributor (Jan 2026) | `elreddy@google.com` |

## Timeline

| Date | Milestone |
|---|---|
| 2026-04-29 | KT call (handover) |
| 2026-05-12 | Initial code mapping / repo setup |
| 2026-05-14 | Connect call — framework updates + clarifications |
| 2026-05-15…16 | Live working session with Zaidul on prompt updates (target) |
| ~2026-05-19 | Conceptual presentation to new client stakeholders (Tuesday) |
| 2026-05-14 onward | Daily pod sync for the next week (per Tarun) |
| 2026-06-15 | Client demo (firm deadline) |
| 2026-07 (TBD) | Full release |
