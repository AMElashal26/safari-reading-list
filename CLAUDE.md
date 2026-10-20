# CLAUDE.md — Safari Reading List tools

- Start by reading `PROGRESS.md` (Snapshot + newest Session Log entry).
- At the end of any session that changes files or makes decisions, append a dated Session Log entry to `PROGRESS.md` (with commit hashes), add Decision-log rows with rationale, and refresh the Snapshot if state changed.
- Never write Reading List data (CSVs, plists, exports, backups) into this folder or the repo. It syncs to iCloud Drive. Data goes to `~/ReadingListExport/`.
- Keep personal routing rules in git-ignored `rules.json` only. Committed code and docs stay content-neutral.
- Any change to `~/Library/Safari/Bookmarks.plist` goes through `readinglist.py --prune` (dry run first, Safari quit, backup + checks).
