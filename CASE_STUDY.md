# Case study: Reverse-engineering and safely bulk-editing Safari's Reading List

**Role:** sole developer · **Duration:** one working session (2026-10-20) · **Platform:** macOS
**Stack:** Python 3.11 (standard library only) · macOS `plutil` · JavaScript for Automation (JXA) over Apple's Foundation framework · vanilla HTML/CSS/JS · git / GitHub CLI · built with Claude Code as an AI pair-programmer

---

## The problem

Over eight years my Safari Reading List had grown to **13,625 saved links**, and 99% of them had never been opened. Safari offers no search across the list, no bulk selection, no export and no API. You can remove items one at a time, or clear the whole list.

I wanted three things:

1. **Visibility:** see what's actually in there, by source, date and topic.
2. **Bulk cleanup:** remove whole categories of content I no longer wanted (about 64% of the list) without touching anything else.
3. **A foundation for a reading system:** turn what's left into a prioritized queue.

## Constraints that shaped the design

| Constraint | Consequence |
|---|---|
| No public API for the Reading List | Work directly with Safari's on-disk data store |
| The data file also holds all bookmarks, favourites, tab groups and iCloud sync state | Any write must be surgical: one wrong byte risks the user's whole browser profile |
| The list syncs across devices through iCloud (CloudKit) | Local edits may not propagate, or may be reverted by sync |
| The data is personal | Exports must stay local-only (outside iCloud Drive), and nothing personal can enter the git repo |

## Approach

### 1. Reverse-engineer the storage format
The Reading List isn't a separate database. It's a folder named `com.apple.ReadingList` inside `~/Library/Safari/Bookmarks.plist`, a **264 MB binary property list**. I mapped the schema of each entry:

- `URLString`, `URIDictionary.title`
- `ReadingList.DateAdded`, `DateLastViewed`, `PreviewText`
- `Sync.ServerID`, an opaque `Sync.Data` blob for CloudKit
- per-item fetch-state metadata

From that I profiled the dataset: 999 distinct domains, 245 duplicate URLs, and how many items were added each year (7,500 in 2025 alone).

### 2. Build a read-only export pipeline
`readinglist.py` loads the list, removes duplicate URLs (keeping the earliest save date and counting repeat saves), routes each item through a rules engine (`rules.json`), and writes:
- **one CSV per collection**, ready to import into Notion or Airtable;
- **`browse.html`**, a single self-contained offline page with full-text search, collection tabs, domain filter, sorting and an "unopened only" toggle. 13k items are embedded as JSON and shown 100 at a time, so it stays fast without a framework or server.

### 3. Build a safe write path (`--prune`)
Write-back follows a guarded sequence. Every step can stop the run without touching Safari's file:

1. **Dry run by default.** It prints exactly what would be removed, grouped by source.
2. **Refuses to run while Safari is open**, so the edit can't collide with Safari writing the file.
3. **Timestamped full backup** of `Bookmarks.plist`.
4. **Edits a working copy**, never the live file.
5. **Checks the result:** the set of remaining item IDs must exactly equal *original minus targets*, and no remaining item may match the exclude rules.
6. **Checks nothing changed in the meantime:** the live file's modification time must be unchanged and Safari still closed.
7. Only then **writes the result over the live file**, keeping its original file attributes.

## Challenges and how I solved them

**Malformed Unicode in Apple's own file.** Python's `plistlib` refused to parse the file. One stored title contained an unpaired UTF-16 surrogate (half of an emoji), which a strict decoder rejects. *Fix:* convert with Apple's `plutil` first. It uses the same CoreFoundation parser Safari does and tolerates the bad character. Then parse the resulting XML.

**The obvious tool crashed.** My first write path used Apple's `PlistBuddy`, deleting entries in descending index order. On a 264 MB file with roughly 8,700 deletions it crashed (`SIGABRT`) and left a corrupt working copy. The verification steps meant the live file was never touched. *Fix:* call **Foundation directly through JXA**: `NSPropertyListSerialization` to read and write the binary format natively, and a single `NSMutableIndexSet` + `removeObjectsAtIndexes:` for one batch deletion. This is the same serializer Safari uses, so everything outside the deleted entries survives byte-for-byte, including sub-second timestamps and the malformed title. A round-trip through Python and XML would have quietly lost or changed both.

**Proving the edit was surgical.** "It didn't crash" isn't evidence. After the write I loaded the backup and the new file and checked that:
- the root sync metadata is identical;
- every bookmarks folder outside the Reading List is identical;
- all 4,876 kept items are identical *and in their original order*;
- the Reading List folder's own metadata is unchanged.

All checks passed.

**Distributed-sync semantics.** Every item carries a CloudKit `ServerID`. Deleting entries from the local file doesn't record a deletion for the sync engine, so other devices keep the items, and a full re-sync could restore them on the Mac. I assessed both options:
- **A:** edit the file directly. Preserves dates and read state, but sync behaviour is uncertain.
- **B:** let Safari clear the list itself (which syncs), then re-add the kept items through Safari's AppleScript `add reading list item` command (also syncs). Original dates are lost.

I chose to ship A, watch for items reappearing, and keep B ready as a fallback.

**Privacy by design.** The code lives in a synced project folder. Data only ever goes to a local, non-synced export directory. Personal routing rules are in a git-ignored `rules.json`, and the repo ships a neutral `rules.example.json`. `.gitignore` blocks plists, CSVs, generated pages and backups, so the repository can never contain personal data.

## Results

- **13,625 → 4,876 items.** 8,749 removed in a single batch, with nothing else in the browser profile changed (checked against the backup as above).
- Duplicates collapsed: **4,861 unique** links now browsable offline in seconds.
- A repeatable, documented CLI: `export`, `--prune` (dry run), `--prune --apply`.
- No third-party dependencies. It runs on any Mac with the system Python 3 and built-in tools.

## What this demonstrates

- **Reverse-engineering an undocumented data format** and working out its schema from the data itself.
- **Defensive engineering around irreversible operations:** dry runs, backups, working copies, invariant checks before commit, and checks for concurrent modification.
- **Debugging across layers:** a Unicode edge case in a binary format, a native tool crashing, and choosing the right abstraction (CoreFoundation over a CLI wrapper or a lossy round-trip).
- **Reasoning about distributed state:** understanding why a local edit and a cloud-synced store can disagree, and designing a fallback.
- **Privacy-conscious delivery:** keeping data and code apart, keeping personal configuration out of version control, and keeping data off cloud storage.
- **Pragmatic tooling:** standard-library Python, platform-native APIs, and a zero-dependency HTML front end.

## Next steps

- Confirm over a few days whether the edit holds against iCloud sync; fall back to option B if not.
- Finish the categorization rules so a "learning" queue appears automatically.
- Import that queue into Notion or Airtable with priority and status fields, for a real read-later workflow.
