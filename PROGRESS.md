# PROGRESS — Safari Reading List tools

Handoff / state-of-the-world doc. Answers **"where are we, and why?"**. No TODO
file yet; open items are under *Current focus*. Append a dated Session Log
entry at the end of any working session; update the Snapshot when state
changes.

## Snapshot (as of 2026-10-20)
- `readinglist.py` CLI works: export (CSV per collection + offline `browse.html`), `--prune` dry run, `--prune --apply`.
- Safari Reading List pruned on this Mac: **13,625 → 4,876 items** (8,749 removed by the `exclude` rules). Checked against the backup: everything outside the removed items is unchanged.
- Backup of the pre-prune file: `~/ReadingListExport/backups/Bookmarks-20261020-020522.plist` (local-only, not in repo).
- **Unconfirmed:** whether iCloud/CloudKit sync restores the removed items on this Mac. Other devices still have them, because local edits don't send deletions.
- `categorize()` only routes `excluded` / `other`. The learning-queue rules are not written yet, so `learning` is empty.
- Private repo: GitHub `AMElashal26/safari-reading-list`.

## Current focus
1. Watch Safari for 1–2 days. If removed items reappear, switch to the fallback (Clear All + AppleScript re-add).
2. Review what remains (4,861 unique items; top sources: medium, github, reddit, youtube, plus grey-area sources listed in `rules.json` notes / the export) and extend the rules.
3. Write the `learning` routing in `categorize()`, then import `learning.csv` into Notion/Airtable as a reading queue. *(Owner's stated direction; Notion vs. Airtable not chosen yet.)*

## Decision log
| Date | Decision | Why / source |
|---|---|---|
| 2026-10-20 | Exports and backups go to `~/ReadingListExport/` (local-only), not the iCloud project folder | Owner's choice; the list contains private material and the project folder syncs to iCloud Drive |
| 2026-10-20 | Parse via `plutil -convert xml1` → `plistlib` | One title holds an unpaired UTF-16 surrogate; `plistlib` rejects the binary file outright |
| 2026-10-20 | Prune only the domains/subreddits already in the rules; grey-area sources deferred | Owner: "just remove the obvious ones … worry about the rest later" |
| 2026-10-20 | Write-back strategy: try a direct plist edit (A), fall back to Clear All + AppleScript re-add (B) | Owner's choice. A keeps dates/read state but may not survive CloudKit sync; B syncs but loses dates |
| 2026-10-20 | Delete through Foundation (`NSPropertyListSerialization` via JXA), not PlistBuddy | PlistBuddy SIGABRT'd on the 264 MB file and left a corrupt working copy; Foundation is Safari's own serializer and is lossless |
| 2026-10-20 | Personal rules in git-ignored `rules.json`; neutral `rules.example.json` committed; names made generic (`--prune`, `is_excluded`) | Repo is meant to show technical work; personal content stays out of code and git history |
| 2026-10-20 | Deferred: `learning` routing rules in `categorize()` | Owner wants to review what remains after pruning first |
| 2026-10-20 | Code explanations live in a separate interactive page (`docs/code-walkthrough.html`), not as inline comments | Owner asked for tutor-style walkthroughs (10 levels). A separate page keeps the portfolio code clean and supports zooming, diagrams and quizzes that comments can't |

## Doc map
| Doc | What it holds |
|---|---|
| `README.md` | Usage, requirements, how it works, sync caveat |
| `CASE_STUDY.md` | Portfolio writeup: problem, approach, challenges, stack, results |
| `PROGRESS.md` | This file |
| `CLAUDE.md` | Instructions for future Claude Code sessions |
| `docs/code-walkthrough.html` | Interactive line → application walkthrough of `readinglist.py` (published privately at https://claude.ai/artifact/2bNZMn2jY2FwSnt8qExbTS). Line notes are keyed to line numbers, so update them when the script changes |
| `rules.json` *(git-ignored)* | Personal exclude/learning routing rules |
| `~/ReadingListExport/` *(off-repo)* | CSVs, `browse.html`, `backups/` |

## How to resume cold
1. Read the Snapshot and the newest Session Log entry.
2. Make sure `rules.json` exists (copy `rules.example.json` if not). The terminal needs Full Disk Access.
3. `python3 readinglist.py --prune` (dry run) shows the current state; `python3 readinglist.py` refreshes the exports.
4. Edit `readinglist.py` (`categorize()` is the main open item). Any `--apply` run needs Safari quit and produces a new backup.
5. Commit, push, and append a Session Log entry here.

## Session log (newest first)
### 2026-10-20
- **Did:** Mapped Safari's Reading List storage (`com.apple.ReadingList` folder in the 264 MB binary `Bookmarks.plist`). Profiled 13,625 items: 99% never opened, 999 domains, 245 duplicate URLs. Built `readinglist.py` (load, dedupe, export to CSV + offline `browse.html`) and `--prune` (dry run → backup → working copy → Foundation batch delete → checks → write).
- **Did:** Pruned 8,749 items: 13,625 → 4,876. The first attempt used PlistBuddy, which crashed; the checks kept Safari untouched. The second attempt used JXA/Foundation and succeeded. Compared old and new files: root metadata, other folders and kept items are identical and in the same order.
- **Did:** Moved the rules into a git-ignored `rules.json`, renamed things generically, added README, CASE_STUDY, PROGRESS and CLAUDE.md, and created the private GitHub repo `AMElashal26/safari-reading-list` (initial commit `ac8660e`). Before committing, a scan of the staged files caught a leftover collection name in `browse_template.html`; it was fixed.
- **Did:** Built `docs/code-walkthrough.html`: an interactive code atlas with notes on about 190 lines, a block → function → layer → module → application zoom ladder, and chapters for the execution trace, data flow, design patterns, mental model, call trees, knowledge and how to read code. Published as a private artifact.
- **Did:** Turned the walkthrough into a reusable personal skill, `~/.claude/skills/code-atlas/` (outside this repo): a data-driven template, `build_atlas.py` (validation, coverage, secret scan), a schema reference, and this project's atlas as the gold-standard example. Rebuilding this atlas through the skill renders identically (260 rows, all chapters).
- **Decided:** see the decision-log rows dated 2026-10-20.
- **Next:** Check Safari for removed items reappearing (iCloud); review the remaining variety; write the learning routing rules.
