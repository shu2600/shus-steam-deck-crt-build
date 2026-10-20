"""Runs ON the Steam Deck (sent by deck_faves.py). Rewrites Steam's shortcuts.vdf from a plan:
keep PC launchers and ES-DE, hide EmuDeck emulator launchers, drop shortcuts with a broken RetroArch core path,
add the planned favourites, unpack their grid art. Steam is shut down first; backup shortcuts.vdf.bak_<time>.
Usage: python3 apply.py plan.json art.tar"""
import sys, os, re, glob, json, struct, time, tarfile, subprocess


def parse(b, i=0):
    d = {}
    while True:
        t = b[i]; i += 1
        if t == 8:
            return d, i
        j = b.index(b"\0", i); k = b[i:j].decode("utf-8", "replace"); i = j + 1
        if t == 0:
            d[k], i = parse(b, i)
        elif t == 1:
            j = b.index(b"\0", i); d[k] = b[i:j].decode("utf-8", "replace"); i = j + 1
        elif t == 2:
            d[k] = struct.unpack("<i", b[i:i + 4])[0]; i += 4
        else:
            raise ValueError(f"vdf type {t}")


def dump(d):
    out = b""
    for k, v in d.items():
        kb = k.encode() + b"\0"
        if isinstance(v, dict):
            out += b"\0" + kb + dump(v)
        elif isinstance(v, int):
            out += b"\x02" + kb + struct.pack("<i", v if v < 2**31 else v - 2**32)
        else:
            out += b"\x01" + kb + str(v).encode() + b"\0"
    return out + b"\x08"


plan = json.load(open(sys.argv[1]))
vdf = glob.glob(os.path.expanduser("~/.local/share/Steam/userdata/*/config/shortcuts.vdf"))[0]
grid = os.path.join(os.path.dirname(vdf), "grid")
os.makedirs(grid, exist_ok=True)

# Steam must not be running, or it writes its copy back over ours
subprocess.run(["steam", "-shutdown"], capture_output=True)
for _ in range(40):
    if subprocess.run(["pgrep", "-x", "steam"], capture_output=True).returncode != 0:
        break
    time.sleep(1)
else:
    subprocess.run(["pkill", "-x", "steam"]); time.sleep(3)

raw = open(vdf, "rb").read()
open(vdf + ".bak_" + time.strftime("%Y%m%d_%H%M%S"), "wb").write(raw)
root, _ = parse(raw, raw.index(b"\0", 1) + 1)   # skip the leading "\0shortcuts\0" header
items = list(root.values())
kept, hidden, dropped = [], 0, 0
for s in items:
    exe = str(s.get("Exe", s.get("exe", ""))); opts = str(s.get("LaunchOptions", ""))
    cmd = (exe + " " + opts).replace('"', "")   # Steam ROM Manager put the arguments into Exe itself
    if "_libretro.so" in cmd and re.search(r" -L /[a-z0-9_]+_libretro\.so", cmd):
        dropped += 1; continue                         # broken core path, never launched
    if "/Emulation/tools/launchers/" in exe:
        s["IsHidden"] = 1; hidden += 1                 # EmuDeck emulator launchers: hidden, not deleted
    if any(str(x.get("AppName", x.get("appname"))) == str(s.get("AppName", s.get("appname"))) and
           x.get("LaunchOptions") == s.get("LaunchOptions") for x in kept):
        continue
    kept.append(s)
names = {str(s.get("AppName", s.get("appname"))) for s in kept}
added = 0
for e in plan:
    if e["AppName"] in names:
        continue
    kept.append({"appid": e["appid"], "AppName": e["AppName"], "Exe": e["Exe"], "StartDir": e["StartDir"], "icon": "",
                 "ShortcutPath": "", "LaunchOptions": e["LaunchOptions"], "IsHidden": 0, "AllowDesktopConfig": 1,
                 "AllowOverlay": 1, "OpenVR": 0, "Devkit": 0, "DevkitGameID": "", "DevkitOverrideAppID": 0,
                 "LastPlayTime": 0, "FlatpakAppID": "", "tags": {str(i): t for i, t in enumerate(e["tags"])}})
    added += 1
open(vdf, "wb").write(b"\0shortcuts\0" + dump({str(i): s for i, s in enumerate(kept)}) + b"\x08")
with tarfile.open(sys.argv[2]) as t:
    t.extractall(grid)
print(f"shortcuts: {len(items)} before, dropped {dropped} broken, hid {hidden} emulator launchers, added {added} favourites, {len(kept)} now")
print("Steam was shut down to write this; it restarts on its own in Game Mode (or start it from the desktop).")
