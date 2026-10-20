"""Give ES-DE on the Steam Deck the same artwork as LaunchBox on the PC.
For every game in deck_sync_list.json that is still in LaunchBox, copy its LaunchBox images into ES-DE's media
folder, named the way ES-DE looks them up: <media dir>/<system>/<type>/<rom name without extension>.<ext>.
Types: covers (Box - Front), 3dboxes (Box - 3D), marquees (Clear Logo), screenshots (Gameplay),
titlescreens (Game Title), backcovers (Box - Back), fanart (Fanart - Background).
Files already on the Deck are skipped. Usage: py -I deck_esde_media.py [--dry]"""
import os, sys, re, json, glob, tarfile, subprocess, io
import xml.etree.ElementTree as ET

import os as _os, sys as _sys
_here = _os.path.dirname(_os.path.abspath(__file__))
_sys.path.insert(0, _here)
import deck_common as D
C = D.C

_info, _err = D.probe()
if not _info:
    sys.exit(f"Can't reach the Deck: {_err}")
MEDIA = _info.get("media") or ""
if not MEDIA:
    sys.exit("No ES-DE media folder found on the Deck (is ES-DE installed via EmuDeck?)")
TYPES = {"Box - Front": "covers", "Box - 3D": "3dboxes", "Clear Logo": "marquees", "Screenshot - Gameplay": "screenshots",
         "Screenshot - Game Title": "titlescreens"}
DRY = "--dry" in sys.argv
safe = lambda t: re.sub(r"[:/\\?*\"<>|']", "_", t)

index = {}   # LaunchBox platform -> {image type -> {safe title lower: path}}


def images(plat, kind):
    key = (plat, kind)
    if key not in index:
        m = {}
        for dp, _d, fs in os.walk(os.path.join(C.LB, "Images", plat, kind)):
            for f in fs:
                mm = re.match(r"^(.*)-0(\d+)\.[^.]+$", f)
                if mm and (mm.group(1).lower() not in m or mm.group(2) == "1"):
                    m[mm.group(1).lower()] = os.path.join(dp, f)
        index[key] = m
    return index[key]


titles = {}   # ApplicationPath (lower) -> (platform, title)
for xml in glob.glob(os.path.join(C.LB, "Data", "Platforms", "*.xml")):
    for g in ET.parse(xml).getroot().findall("Game"):
        titles[(g.findtext("ApplicationPath") or "").lower()] = (g.findtext("Platform"), g.findtext("Title"))

synced = json.load(open(os.path.join(_here, "deck_sync_list.json"), encoding="utf-8"))
plan, size = [], 0
for e in synced:
    t = titles.get(e["src"].lower())
    if not t:
        continue
    plat, title = t
    system, rom = e["dst"].split("/", 1)
    stem = os.path.splitext(os.path.basename(rom))[0]
    for kind, folder in TYPES.items():
        src = images(plat, kind).get(safe(title).lower())
        if src:
            plan.append((src, f"{system}/{folder}/{stem}{os.path.splitext(src)[1].lower()}"))
            size += os.path.getsize(src)
print(f"{len(plan)} images for {len({p[1].split('/')[0] + p[1].split('/', 2)[2].rsplit('.', 1)[0] for p in plan})} games, {size / 1e9:.1f} GB")
if DRY:
    sys.exit()

# what's there already (skip), then stream the rest as one tar over ssh
have = set(D.ssh(f'cd "{MEDIA}" 2>/dev/null && find . -type f', timeout=600).stdout.decode("utf-8", "replace").replace("./", "").splitlines())
todo = [p for p in plan if p[1] not in have]
print(f"{len(todo)} to send")
proc = subprocess.Popen(D.ssh_args() + [f'mkdir -p "{MEDIA}" && tar -xf - -C "{MEDIA}"'], stdin=subprocess.PIPE)
with tarfile.open(fileobj=proc.stdin, mode="w|") as tf:
    for i, (src, dst) in enumerate(todo, 1):
        tf.add(src, arcname=dst)
        if i % 5000 == 0:
            print(f"  {i}/{len(todo)}", flush=True)
proc.stdin.close(); proc.wait()
print("done, exit", proc.returncode)
