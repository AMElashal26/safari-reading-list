#!/usr/bin/env python3
"""Export, categorize and prune Safari's Reading List.

Exports are written to a local-only folder (not iCloud). Safari's
Bookmarks.plist is only modified by `--prune --apply`, after a backup.

    python3 readinglist.py                 # export to ~/ReadingListExport
    python3 readinglist.py --out DIR       # export somewhere else
    python3 readinglist.py --prune         # dry run: what would be removed
    python3 readinglist.py --prune --apply # back up, then edit Safari (quit it first)

Routing rules live in rules.json (git-ignored); see rules.example.json.
"""
import argparse
import csv
import json
import plistlib
import shutil
import subprocess
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).parent
BOOKMARKS = Path.home() / "Library/Safari/Bookmarks.plist"
DEFAULT_OUT = Path.home() / "ReadingListExport"
COLLECTIONS = ("learning", "other", "excluded")


def load_rules():
    """Read rules.json, falling back to the committed example."""
    path = HERE / "rules.json"
    if not path.exists():
        path = HERE / "rules.example.json"
    rules = json.loads(path.read_text(encoding="utf-8"))
    return {
        "exclude_domains": set(rules["exclude"]["domains"]),
        "exclude_subreddits": set(rules["exclude"]["subreddits"]),
        "learning_domains": set(rules["learning"]["domains"]),
    }


RULES = load_rules()


# ---------------------------------------------------------------- loading

def load_root(path=BOOKMARKS):
    """Parse Bookmarks.plist.

    Safari's binary plist can contain malformed UTF-16 (half an emoji in a
    title) that Python's plistlib rejects, so convert via Apple's plutil first.
    """
    with tempfile.TemporaryDirectory() as tmp:
        xml = Path(tmp) / "bookmarks.xml"
        subprocess.run(["plutil", "-convert", "xml1", "-o", str(xml), str(path)], check=True)
        with open(xml, "rb") as f:
            return plistlib.load(f)


def reading_list_index(root):
    """Position of the Reading List folder within the root's Children."""
    return next(n for n, c in enumerate(root.get("Children", [])) if c.get("Title") == "com.apple.ReadingList")


def load_items(path=BOOKMARKS):
    """Return Reading List entries as flat dicts, oldest first.

    Each item keeps `index`, its position in the Reading List folder on disk.
    """
    root = load_root(path)
    folder = root["Children"][reading_list_index(root)]
    items = []
    for index, raw in enumerate(folder.get("Children", [])):
        rl = raw.get("ReadingList", {})
        url = raw.get("URLString", "")
        parsed = urlparse(url)
        parts = parsed.path.split("/")
        items.append({
            "index": index,
            "title": raw.get("URIDictionary", {}).get("title") or url,
            "url": url,
            "domain": parsed.netloc.lower().removeprefix("www.").removeprefix("m."),
            "subreddit": parts[2].lower() if len(parts) > 2 and parts[1] == "r" else "",
            "added": rl.get("DateAdded"),
            "viewed": rl.get("DateLastViewed"),
            "preview": (rl.get("PreviewText") or "").strip(),
            "uuid": raw.get("WebBookmarkUUID", ""),
        })
    items.sort(key=lambda i: i["added"] or datetime.min)
    return items


def dedupe(items):
    """Collapse identical URLs, keeping the earliest save and counting repeats."""
    seen = {}
    for item in items:
        if item["url"] in seen:
            seen[item["url"]]["saves"] += 1
        else:
            seen[item["url"]] = {**item, "saves": 1}
    return list(seen.values())


# ---------------------------------------------------------------- categorizing

def matches_domain(item, domains):
    """True if the item's domain, or a parent domain, is in `domains`."""
    d = item["domain"]
    return any(d == x or d.endswith("." + x) for x in domains)


def is_excluded(item):
    return matches_domain(item, RULES["exclude_domains"]) or item["subreddit"] in RULES["exclude_subreddits"]


def categorize(item):
    """Return which collection an item belongs to: "learning", "other" or "excluded".

    `item` has: title, url, domain, subreddit, added, viewed, preview, saves.
    RULES holds the domain/subreddit sets from rules.json.
    """
    # TODO(you): decide the routing rules for the learning queue.
    return "excluded" if is_excluded(item) else "other"


# ---------------------------------------------------------------- pruning

# argv: plist path, Reading List folder index, file of item indexes (one per line).
DELETE_JXA = """
ObjC.import('Foundation');
function run(argv) {
  const [path, folder, targets] = argv;
  const root = $.NSPropertyListSerialization.propertyListWithDataOptionsFormatError(
    $.NSData.dataWithContentsOfFile(path), 1 /* mutable containers */, null, null);
  if (root.isNil()) throw new Error('could not parse ' + path);
  const items = root.objectForKey('Children').objectAtIndex(Number(folder)).objectForKey('Children');
  const doomed = $.NSMutableIndexSet.indexSet;
  $.NSString.stringWithContentsOfFileEncodingError(targets, $.NSUTF8StringEncoding, null).js
    .trim().split('\\n').forEach(n => doomed.addIndex(Number(n)));
  items.removeObjectsAtIndexes(doomed);
  const data = $.NSPropertyListSerialization.dataWithPropertyListFormatOptionsError(
    root, 200 /* binary v1.0 */, 0, null);
  if (data.isNil() || !data.writeToFileAtomically(path, true)) throw new Error('could not write ' + path);
}
"""


def safari_running():
    return subprocess.run(["pgrep", "-x", "Safari"], capture_output=True).returncode == 0


def prune(apply, out):
    """Delete is_excluded() items from Bookmarks.plist (dry run unless apply).

    Deletion runs on a working copy through Foundation (DELETE_JXA), so the
    file is rewritten in Safari's own binary format and every other key —
    sync metadata, bookmarks, sub-second dates, the malformed title — is
    carried over untouched. (PlistBuddy aborts on a file this size.)
    """
    items = load_items()
    doomed = [i for i in items if is_excluded(i)]
    print(f"{len(doomed)} of {len(items)} Reading List items match the exclude rules:")
    for source, n in Counter(i["subreddit"] and f"reddit r/{i['subreddit']}" or i["domain"] for i in doomed).most_common():
        print(f"  {n:6}  {source}")
    if not apply:
        print("Dry run — nothing changed. Re-run with --apply (Safari must be quit).")
        return
    if not doomed:
        return
    if safari_running():
        raise SystemExit("Safari is running — quit it first (⌘Q) and re-run.")

    backups = out / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = backups / f"Bookmarks-{stamp}.plist"
    work = backups / f"Bookmarks-{stamp}-pruned.plist"
    shutil.copy2(BOOKMARKS, backup)
    shutil.copy2(BOOKMARKS, work)
    mtime = BOOKMARKS.stat().st_mtime
    print(f"Backup: {backup}")

    folder = reading_list_index(load_root(work))
    targets = backups / f"Bookmarks-{stamp}-targets.txt"
    targets.write_text("\n".join(str(i["index"]) for i in doomed))
    subprocess.run(["osascript", "-l", "JavaScript", "-e", DELETE_JXA,
                    str(work), str(folder), str(targets)], check=True)
    targets.unlink()

    remaining = load_items(work)
    expected = {i["uuid"] for i in items} - {i["uuid"] for i in doomed}
    if {i["uuid"] for i in remaining} != expected or any(is_excluded(i) for i in remaining):
        raise SystemExit(f"Verification failed — Safari untouched. Working copy left at {work}")
    if BOOKMARKS.stat().st_mtime != mtime or safari_running():
        raise SystemExit("Bookmarks.plist changed while working (sync agent?) — Safari untouched. Try again.")

    shutil.copyfile(work, BOOKMARKS)  # write into the existing file, keeping its attributes
    work.unlink()
    print(f"Done: Reading List now has {len(remaining)} items. Relaunch Safari.")


# ---------------------------------------------------------------- exporting

def fmt(dt):
    return dt.strftime("%Y-%m-%d") if dt else ""


def write_csvs(items, out):
    fields = ["title", "url", "domain", "added", "viewed", "saves", "preview"]
    for name in COLLECTIONS:
        with open(out / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            for i in items:
                if i["collection"] == name:
                    w.writerow({**i, "added": fmt(i["added"]), "viewed": fmt(i["viewed"])})


def write_html(items, out):
    rows = [
        [i["title"], i["url"], i["domain"], fmt(i["added"]), 1 if i["viewed"] else 0,
         i["preview"][:280], i["collection"], i["saves"]]
        for i in items
    ]
    data = json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")
    template = (HERE / "browse_template.html").read_text(encoding="utf-8")
    (out / "browse.html").write_text(template.replace("/*__DATA__*/[]", data), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--prune", action="store_true", help="remove excluded items from Safari (dry run)")
    ap.add_argument("--apply", action="store_true", help="with --prune: actually modify Bookmarks.plist")
    args = ap.parse_args()

    if args.prune:
        return prune(args.apply, args.out)

    items = dedupe(load_items())
    for i in items:
        i["collection"] = categorize(i)

    args.out.mkdir(parents=True, exist_ok=True)
    write_csvs(items, args.out)
    write_html(items, args.out)

    counts = Counter(i["collection"] for i in items)
    print(f"{len(items)} unique items → {args.out}")
    for name in COLLECTIONS:
        print(f"  {name:9} {counts[name]:6}")
    unsorted = Counter(i["domain"] for i in items if i["collection"] == "other")
    print("top domains still in 'other':", ", ".join(f"{d} {n}" for d, n in unsorted.most_common(10)))


if __name__ == "__main__":
    main()
