"""Work out which games from your LaunchBox go to the Steam Deck's EmuDeck roms folders.
Per system: "all" (every game), "playlists" (only games in your LaunchBox playlists) or "none".
Writes deck_sync_list.json: [{"src": PC path, "dst": "<emudeck folder>/<file>", "size": bytes, "plat": platform}]
Usage: py -I deck_plan.py            (defaults: cartridge systems whole, disc systems playlists only)"""
import glob, json, os, sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deck_common as D  # noqa: E402

LB = D.C.LB
ARCADE_BIOS = ["neogeo", "pgm", "cpzn1", "cpzn2", "naomi", "awbios", "stvbios", "skns", "decocass", "nss", "playch10",
               "megaplay", "qsound", "isgsm", "hng64", "konamigx", "atarisy1", "coh1000c", "coh1000t", "taitofx1", "tps",
               "sys573", "aleck64", "crysbios"]


def library():
    """{game id: (platform, file path, title)} and the ids that sit in a playlist."""
    games = {}
    for f in glob.glob(os.path.join(LB, "Data", "Platforms", "*.xml")):
        for g in ET.parse(f).getroot().findall("Game"):
            p = g.findtext("ApplicationPath") or ""
            if p and not os.path.isabs(p):
                p = os.path.normpath(os.path.join(LB, p))
            games[g.findtext("ID")] = (g.findtext("Platform"), p, g.findtext("Title"))
    listed = set()
    for f in glob.glob(os.path.join(LB, "Data", "Playlists", "*.xml")):
        for pg in ET.parse(f).getroot().findall("PlaylistGame"):
            listed.add(pg.findtext("GameId"))
    return games, listed


def files_for(path):
    out = [path]
    if path.lower().endswith(".m3u") and os.path.exists(path):          # multi-disc: the m3u plus every disc in it
        d = os.path.dirname(path)
        for line in open(path, encoding="utf-8", errors="ignore"):
            line = line.strip()
            if line and not line.startswith("#"):
                out.append(os.path.join(d, line))
    return out


def default_modes(games):
    plats = {p for p, _f, _t in games.values() if p in D.FOLDER}
    return {p: ("all" if p in D.CARTS else "playlists") for p in plats}


def build(modes, games=None, listed=None):
    if games is None:
        games, listed = library()
    items = []
    for gid, (plat, path, title) in games.items():
        mode = modes.get(plat, "none")
        if plat not in D.FOLDER or not path or mode == "none" or (mode == "playlists" and gid not in listed):
            continue
        for p in files_for(path):
            if os.path.isfile(p):
                items.append({"src": p, "dst": D.FOLDER[plat] + "/" + os.path.basename(p), "size": os.path.getsize(p), "plat": plat})
    arcade_dirs = {os.path.dirname(it["src"]) for it in items if it["plat"] == "Arcade"}
    for b in ARCADE_BIOS:                                                # BIOS sets the arcade games need, from the same folders
        for d in arcade_dirs:
            p = os.path.join(d, b + ".zip")
            if os.path.isfile(p):
                items.append({"src": p, "dst": "arcade/" + b + ".zip", "size": os.path.getsize(p), "plat": "Arcade"}); break
    seen, uniq = set(), []
    for it in items:
        if it["dst"].lower() not in seen:
            seen.add(it["dst"].lower()); uniq.append(it)
    return uniq


def summary(items):
    by = {}
    for it in items:
        n, s = by.get(it["plat"], (0, 0)); by[it["plat"]] = (n + 1, s + it["size"])
    return by


def sizes(games, listed):
    """{platform: (all files, all bytes, playlist files, playlist bytes)} for the wizard's table."""
    out = {}
    for gid, (plat, path, _t) in games.items():
        if plat not in D.FOLDER or not path:
            continue
        b = sum(os.path.getsize(p) for p in files_for(path) if os.path.isfile(p))
        a = out.setdefault(plat, [0, 0, 0, 0]); a[0] += 1; a[1] += b
        if gid in listed:
            a[2] += 1; a[3] += b
    return out


def save(items):
    json.dump(items, open(os.path.join(D.HERE, "deck_sync_list.json"), "w", encoding="utf-8"), indent=0)


if __name__ == "__main__":
    g, l = library()
    items = build(default_modes(g), g, l)
    save(items)
    for plat, (n, s) in sorted(summary(items).items(), key=lambda x: -x[1][1]):
        print(f"{s / 1e9:8.2f} GB  {n:5d}  {plat}")
    print(f"TOTAL {sum(i['size'] for i in items) / 1e9:.1f} GB, {len(items)} files")
