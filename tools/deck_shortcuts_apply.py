"""Runs ON the Steam Deck (sent by deck_faves.py). Puts your LaunchBox favourites into Steam's shortcuts.vdf.
It only touches the shortcuts this build made (tagged Favourites, launched through flatpak RetroArch / Dolphin /
PPSSPP): last run's are swapped for this run's. Every other shortcut you have is left exactly as it was.
Steam is shut down first (or it writes its copy back over ours); the old file is kept as shortcuts.vdf.bak_<time>.
Usage: python3 apply.py plan.json art.tar"""
import sys, os, glob, json, struct, time, tarfile, subprocess

OURS = ("run org.libretro.RetroArch -L ", "run org.DolphinEmu.dolphin-emu ", "run org.ppsspp.PPSSPP ")


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


def ours(s):
    """A shortcut this build made: a Favourites tag, flatpak as the program, one of our launch lines."""
    tags = s.get("tags") or {}
    tags = tags.values() if isinstance(tags, dict) else []
    exe = str(s.get("Exe", s.get("exe", ""))).replace('"', "")
    return ("Favourites" in tags and exe == "/usr/bin/flatpak"
            and str(s.get("LaunchOptions", "")).startswith(OURS))


def steam_user():
    """The Steam account signed in most recently on this Deck (its localconfig.vdf is the newest)."""
    users = [d for d in glob.glob(os.path.expanduser("~/.local/share/Steam/userdata/*")) if os.path.basename(d).isdigit()
             and os.path.basename(d) != "0"]
    if not users:
        sys.exit("No Steam account found on the Deck. Sign in to Steam on it once, then run this again.")
    return max(users, key=lambda d: max((os.path.getmtime(p) for p in glob.glob(os.path.join(d, "config", "*"))), default=0))


plan = json.load(open(sys.argv[1]))
cfg = os.path.join(steam_user(), "config")
vdf = os.path.join(cfg, "shortcuts.vdf")
grid = os.path.join(cfg, "grid")
os.makedirs(grid, exist_ok=True)

# Steam must not be running, or it writes its copy back over ours
subprocess.run(["steam", "-shutdown"], capture_output=True)
for _ in range(40):
    if subprocess.run(["pgrep", "-x", "steam"], capture_output=True).returncode != 0:
        break
    time.sleep(1)
else:
    subprocess.run(["pkill", "-x", "steam"]); time.sleep(3)

items = []
if os.path.exists(vdf):
    raw = open(vdf, "rb").read()
    open(vdf + ".bak_" + time.strftime("%Y%m%d_%H%M%S"), "wb").write(raw)
    if raw.strip(b"\0\x08"):
        root, _ = parse(raw, raw.index(b"\0", 1) + 1)   # skip the leading "\0shortcuts\0" header
        items = list(root.values())
kept = [s for s in items if not ours(s)]
removed = len(items) - len(kept)
for e in plan:
    kept.append({"appid": e["appid"], "AppName": e["AppName"], "Exe": e["Exe"], "StartDir": e["StartDir"], "icon": "",
                 "ShortcutPath": "", "LaunchOptions": e["LaunchOptions"], "IsHidden": 0, "AllowDesktopConfig": 1,
                 "AllowOverlay": 1, "OpenVR": 0, "Devkit": 0, "DevkitGameID": "", "DevkitOverrideAppID": 0,
                 "LastPlayTime": 0, "FlatpakAppID": "", "tags": {str(i): t for i, t in enumerate(e["tags"])}})
tmp = vdf + ".new"
open(tmp, "wb").write(b"\0shortcuts\0" + dump({str(i): s for i, s in enumerate(kept)}) + b"\x08")
os.replace(tmp, vdf)
with tarfile.open(sys.argv[2]) as t:
    if hasattr(tarfile, "data_filter"):
        t.extractall(grid, filter="data")
    else:
        t.extractall(grid)
print(f"shortcuts: {len(items)} before, swapped {removed} favourites from last time for {len(plan)}, "
      f"left your other {len(items) - removed} alone, {len(kept)} now")
print("Steam was shut down to write this; it restarts on its own in Game Mode (or start it from the desktop).")
print("shortcuts-done")
