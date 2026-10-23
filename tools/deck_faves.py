"""Put your LaunchBox favourites into the Steam Deck's Steam library as proper shortcuts, with box art.
- finds each favourite's ROM on the Deck (same file name as on the PC, under the EmuDeck roms folders)
- builds a launch command per system (flatpak RetroArch + the right core, or Dolphin / PPSSPP)
- copies box front, logo and screenshot from LaunchBox into Steam's grid folder
- updates shortcuts.vdf: swaps the favourites this build added last time for this time's, and leaves every other
  shortcut alone. Steam is shut down while it writes; the old file is kept as shortcuts.vdf.bak_<time>.
Usage: py -I deck_faves.py [--dry]"""
import os, sys, re, json, glob, zlib, subprocess, tempfile, shutil
import xml.etree.ElementTree as ET

import os as _os, sys as _sys
_here = _os.path.dirname(_os.path.abspath(__file__))
_sys.path.insert(0, _here)
import deck_common as D
C = D.C

_info, _err = D.probe()
if not _info:
    sys.exit(f"Can't reach the Deck: {_err}")
ROMS = _info["roms"]
CORES = "/home/deck/.var/app/org.libretro.RetroArch/config/retroarch/cores"
FOLDER_OLD = {"Atari 2600": "atari2600", "Atari Lynx": "atarilynx", "Atari ST": "atarist", "Commodore Amiga": "amiga",
          "Nintendo 3DS": "3ds", "Nintendo 64": "n64", "Nintendo DS": "nds", "Nintendo GameCube": "gamecube",
          "SNK Neo Geo AES": "neogeo", "SNK Neo Geo Pocket Color": "ngpc", "Sega Genesis": "megadrive",
          "Super Nintendo Entertainment System": "snes", "Sinclair ZX Spectrum": "zxspectrum", "Sony PSP": "psp",
          "Arcade": "arcade"}
CORE = {"Atari 2600": "stella", "Atari Lynx": "handy", "Atari ST": "hatari", "Commodore Amiga": "puae",
        "Nintendo 3DS": "azahar", "Nintendo 64": "mupen64plus_next", "Nintendo DS": "melonds",
        "SNK Neo Geo AES": "fbneo", "SNK Neo Geo Pocket Color": "mednafen_ngp", "Sega Genesis": "genesis_plus_gx",
        "Super Nintendo Entertainment System": "snes9x", "Sinclair ZX Spectrum": "fuse", "Arcade": "mame"}
FOLDER = {k: v for k, v in D.FOLDER.items() if k in CORE or k in ("Nintendo GameCube", "Sony PSP")}
DRY = "--dry" in sys.argv


def ssh(cmd, data=None):
    return D.ssh(cmd, data)


def launch(plat, rom):
    q = '"' + rom + '"'
    if plat == "Nintendo GameCube":
        return "run org.DolphinEmu.dolphin-emu -b -e " + q
    if plat == "Sony PSP":
        return "run org.ppsspp.PPSSPP -f -g " + q
    return f'run org.libretro.RetroArch -L "{CORES}/{CORE[plat]}_libretro.so" {q}'


def appid(exe, name):   # Steam's id for a non-Steam shortcut
    return zlib.crc32((exe + name).encode("utf-8")) | 0x80000000


def art(plat, title, kind):
    safe = re.sub(r"[:/\\?*\"<>|']", "_", title)
    for p in glob.glob(os.path.join(glob.escape(os.path.join(C.LB, "Images", plat, kind)), "**", glob.escape(safe) + "-0*.*"), recursive=True):
        return p
    return None


# 1. favourites from LaunchBox
favs = []
for plat in FOLDER:
    xml = os.path.join(C.LB, "Data", "Platforms", plat + ".xml")
    if not os.path.exists(xml):
        continue
    for g in ET.parse(xml).getroot().findall("Game"):
        if g.findtext("Favorite") == "true":
            favs.append((plat, g.findtext("Title"), os.path.basename(g.findtext("ApplicationPath") or "")))

# 2. where each one is on the Deck (one ssh call)
FINDER = ("import json,os,sys,re\nq=json.load(sys.stdin);out={}\n"
          "norm=lambda s: re.sub(r'[^a-z0-9]','',re.sub(r'\\(.*?\\)|\\[.*?\\]','',s.lower()))\n"
          "for i,(d,b,t) in q.items():\n"
          " fs_all=[(dp,f) for dp,_,fs in os.walk(d) for f in fs]\n"
          " hit=[os.path.join(dp,f) for dp,f in fs_all if f==b]\n"
          " if not hit:  # same game under another file name: match the title (CD2/Disc 2 never)\n"
          "  hit=[os.path.join(dp,f) for dp,f in fs_all if norm(os.path.splitext(f)[0])==norm(t) and not re.search(r'(?i)(cd|disc|disk)\\s*[2-9]',f)]\n"
          " if hit: out[i]=sorted(hit,key=len)[0]\n"
          "print(json.dumps(out))\n")
query = {str(i): (f"{ROMS}/{FOLDER[p]}", b, t) for i, (p, t, b) in enumerate(favs)}   # names go as data, never through a shell
def must(r, what):
    """Stop with an error (so the wizard reports it) if a step on the Deck failed."""
    if r.returncode != 0:
        sys.exit(f"{what} failed on the Deck (exit {r.returncode}): {r.stderr.decode('utf-8', 'replace').strip()[-400:]}")
    return r


must(ssh("cat > /tmp/deckfaves_find.py", FINDER.encode()), "Sending the game finder")
res = must(ssh("python3 /tmp/deckfaves_find.py", json.dumps(query).encode()), "Finding your favourites")
where = {int(k): v for k, v in json.loads(res.stdout.decode("utf-8") or "{}").items()}

SHORT = {"Sinclair ZX Spectrum": "Spectrum", "SNK Neo Geo Pocket Color": "NGPC", "Arcade": "Arcade", "Atari 2600": "2600",
         "Nintendo 64": "N64", "Super Nintendo Entertainment System": "SNES", "Sega Genesis": "Mega Drive"}
seen, clash = set(), {}
for i, (plat, title, base) in enumerate(favs):
    clash.setdefault(title.strip(), set()).add(plat)
entries, missing = [], []
stage = tempfile.mkdtemp(prefix="deckfaves_")
for i, (plat, title, base) in enumerate(favs):
    if i not in where:
        missing.append(f"{plat}: {title}"); continue
    if (plat, title.strip()) in seen:          # e.g. MAME's Pac-Man and Puck Man both titled Pac-Man: keep one
        continue
    seen.add((plat, title.strip()))
    lb_title = title
    title = title.strip()
    if len(clash[title]) > 1:                  # same name on two systems: say which
        title = f"{title} ({SHORT.get(plat, plat)})"
    exe = '"/usr/bin/flatpak"'
    aid = appid(exe, title)
    files = {}
    for kind, suffix in (("Box - Front", "p"), ("Clear Logo", "_logo"), ("Screenshot - Gameplay", "_hero"), ("Screenshot - Gameplay", "")):
        src = art(plat, lb_title, kind)
        if src:
            dst = f"{aid}{suffix}{os.path.splitext(src)[1].lower()}"
            shutil.copy2(src, os.path.join(stage, dst)); files[suffix] = dst
    entries.append({"appid": aid, "AppName": title, "Exe": exe, "StartDir": '"/usr/bin/"', "LaunchOptions": launch(plat, where[i]),
                    "tags": ["Favourites", plat], "art": files})
print(f"{len(favs)} favourites, {len(entries)} found on the Deck")
if missing:
    print("not on the Deck:", "; ".join(missing))
if DRY:
    for e in entries:
        print(" ", e["AppName"], "|", e["LaunchOptions"][:110], "|", sorted(e["art"]))
    sys.exit()

# 3. send art + plan, then rewrite shortcuts.vdf on the Deck (Steam shut down meanwhile)
tar = os.path.join(tempfile.gettempdir(), "deckfaves_art.tar")
subprocess.run(["tar", "-cf", tar.replace("\\", "/"), "-C", stage.replace("\\", "/"), "."], check=True)
must(ssh("rm -rf /tmp/deckfaves && mkdir -p /tmp/deckfaves"), "Making a work folder")
r = subprocess.run(["scp"] + D.ssh_args()[1:-1] + [tar, f"{D.host()}:/tmp/deckfaves/art.tar"], capture_output=True)
if r.returncode != 0:
    sys.exit(f"Sending the box art failed: {r.stderr.decode('utf-8', 'replace')[:300]}")
print("art sent")
must(ssh("cat > /tmp/deckfaves/plan.json", json.dumps(entries).encode()), "Sending the favourites list")
must(ssh("cat > /tmp/deckfaves/apply.py", open(os.path.join(_here, "deck_shortcuts_apply.py"), "rb").read()), "Sending the shortcut writer")
res = ssh("python3 /tmp/deckfaves/apply.py /tmp/deckfaves/plan.json /tmp/deckfaves/art.tar")
print(res.stdout.decode("utf-8", "replace"), res.stderr.decode("utf-8", "replace")[-800:])
if res.returncode != 0 or b"shortcuts-done" not in res.stdout:
    sys.exit("Writing the Steam shortcuts failed on the Deck. Your old shortcuts file is kept as shortcuts.vdf.bak_<time>.")
