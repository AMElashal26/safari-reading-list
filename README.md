# Safari Reading List tools

Export, browse, categorize and bulk-prune Safari's Reading List on macOS: something Safari itself has no UI or API for.

See **[CASE_STUDY.md](CASE_STUDY.md)** for the design, challenges and results.

## Requirements
- macOS with Safari. Python 3.9+ (standard library only).
- Your terminal needs **Full Disk Access** (System Settings → Privacy & Security) to read `~/Library/Safari`.

## Usage
```sh
cp rules.example.json rules.json          # then edit your routing rules

python3 readinglist.py                    # export → ~/ReadingListExport/{*.csv, browse.html}
python3 readinglist.py --prune            # dry run: list items matching rules.json "exclude"
python3 readinglist.py --prune --apply    # quit Safari first; backs up, edits a copy, verifies, then writes
```

Exports and backups go to `~/ReadingListExport/` (local-only, outside iCloud). Open `browse.html` in any browser to search and filter the list offline.

## How it works
- **Read:** `Bookmarks.plist` → `plutil -convert xml1` (tolerates malformed UTF-16 in titles) → `plistlib`.
- **Write:** Foundation's `NSPropertyListSerialization` via JXA (`osascript -l JavaScript`). It removes all target items in one batch and writes the file back in Safari's native binary format.
- **Safety:** dry run by default; refuses while Safari is running; timestamped backup; checks the result before writing; aborts if the live file changed meanwhile.

## Caveat: iCloud sync
Reading List items sync via CloudKit. Edits to the local file don't send deletions to your other devices. If deleted items come back, the fallback is to *Clear All Items* in Safari, then re-add the kept items with Safari's AppleScript `add reading list item` command.

## Files
| File | Purpose |
|---|---|
| `readinglist.py` | CLI: load, dedupe, categorize, export, prune |
| `browse_template.html` | Offline browser page; the export embeds the data into it |
| `rules.example.json` | Template for the git-ignored `rules.json` |
| `CASE_STUDY.md` | Portfolio writeup |
| `PROGRESS.md` | Handoff doc: state, decisions, session log |
