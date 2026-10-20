"""Shared bits for the Steam Deck tools: settings, SSH to the Deck, and finding where EmuDeck put things.

Settings come from lb_settings.json next to this file (the same file the PC build uses), section "steam_deck":
  {"host": "steamdeck.local", "user": "deck", "roms": "", "media": ""}   empty = found on the Deck by probe()
Everything here talks to the Deck over SSH with a key, so no password is ever stored or typed by these tools."""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lbconfig as C  # noqa: E402  paths from lb_settings.json

KEY = os.path.expanduser(os.path.join("~", ".ssh", "id_ed25519"))
DECK = dict(C.DECK or {})
RA = "/home/deck/.var/app/org.libretro.RetroArch/config/retroarch"   # RetroArch flatpak, as EmuDeck installs it

# LaunchBox platform -> EmuDeck roms folder
FOLDER = {
    "Atari 2600": "atari2600", "Atari 5200": "atari5200", "Atari 7800": "atari7800", "Atari Jaguar": "atarijaguar",
    "Atari Lynx": "atarilynx", "Atari ST": "atarist", "ColecoVision": "colecovision", "Commodore Amiga": "amiga",
    "GCE Vectrex": "vectrex", "Mattel Intellivision": "intellivision", "NEC TurboGrafx-16": "tg16",
    "Nintendo 3DS": "3ds", "Nintendo 64": "n64", "Nintendo DS": "nds", "Nintendo GameCube": "gamecube",
    "Nintendo Wii": "wii", "Sony Playstation 2": "ps2", "Sony Playstation": "psx", "Nintendo Switch": "switch",
    "SNK Neo Geo AES": "neogeo", "SNK Neo Geo Pocket Color": "ngpc", "Sega Genesis": "megadrive", "Sega 32X": "sega32x",
    "Sega Dreamcast": "dreamcast", "Sega Saturn": "saturn", "Sega CD": "segacd", "Sega Master System": "mastersystem",
    "Sega Game Gear": "gamegear", "Super Nintendo Entertainment System": "snes", "Nintendo Entertainment System": "nes",
    "Nintendo Game Boy": "gb", "Nintendo Game Boy Color": "gbc", "Nintendo Game Boy Advance": "gba",
    "Sinclair ZX Spectrum": "zxspectrum", "Sony PSP": "psp", "Arcade": "arcade", "Commodore 64": "c64",
    "Amstrad CPC": "amstradcpc", "MS-DOS": "dos",
}
# systems small enough to copy whole by default; the rest default to the games in your playlists
CARTS = {"Atari 2600", "Atari 5200", "Atari 7800", "Atari Jaguar", "Atari Lynx", "ColecoVision", "GCE Vectrex",
         "Mattel Intellivision", "NEC TurboGrafx-16", "SNK Neo Geo Pocket Color", "Sega Genesis", "Sega 32X",
         "Super Nintendo Entertainment System", "Nintendo Entertainment System", "Nintendo Game Boy",
         "Nintendo Game Boy Color", "Nintendo Game Boy Advance", "Sega Master System", "Sega Game Gear", "Nintendo DS",
         "Sinclair ZX Spectrum", "Commodore Amiga", "Atari ST", "Commodore 64", "Amstrad CPC"}


def host():
    h = DECK.get("host") or "steamdeck.local"
    return h if "@" in h else f"{DECK.get('user') or 'deck'}@{h}"


def ssh_args(batch=True):
    a = ["ssh", "-o", "ConnectTimeout=8", "-o", "ServerAliveInterval=30"]
    if os.path.exists(KEY):
        a += ["-i", KEY, "-o", "IdentitiesOnly=yes"]
    if batch:
        a += ["-o", "BatchMode=yes"]
    return a + [host()]


def ssh(cmd, data=None, timeout=600):
    """Run a command on the Deck. data goes in on stdin (file names travel as data, never through a shell)."""
    return subprocess.run(ssh_args() + [cmd], input=data, capture_output=True, timeout=timeout,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


PROBE = r'''
import json, os, glob, shutil, subprocess
cands = [os.path.expanduser("~/Emulation")] + sorted(glob.glob("/run/media/*/*/Emulation")) + sorted(glob.glob("/run/media/*/Emulation"))
emu = next((c for c in cands if os.path.isdir(os.path.join(c, "roms"))), "")
def free(p):
    try:
        return shutil.disk_usage(p).free
    except Exception:
        return 0
media = ""
for s in (os.path.expanduser("~/ES-DE/settings/es_settings.xml"), os.path.expanduser("~/.emulationstation/es_settings.xml")):
    if os.path.exists(s):
        for line in open(s, encoding="utf-8", errors="ignore"):
            if 'name="MediaDirectory"' in line and 'value="' in line:
                media = line.split('value="')[1].split('"')[0]
if not media and emu:
    media = os.path.join(emu, "tools", "downloaded_media")
fp = subprocess.run(["flatpak", "list", "--app", "--columns=application"], capture_output=True, text=True).stdout.split()
ra = os.path.expanduser("~/.var/app/org.libretro.RetroArch/config/retroarch")
print(json.dumps({"emulation": emu, "roms": os.path.join(emu, "roms") if emu else "", "free": free(emu or os.path.expanduser("~")),
                  "media": media, "flatpaks": fp, "retroarch": os.path.isdir(ra),
                  "mega_bezel": os.path.isdir(os.path.join(ra, "shaders", "shaders_slang", "bezel", "Mega_Bezel")),
                  "duimon": os.path.isdir(os.path.join(ra, "shaders", "Mega_Bezel_Packs", "Duimon-Mega-Bezel")),
                  "thenamec": os.path.isdir(os.path.join(ra, "shaders", "Mega_Bezel_Packs", "thenamec-commodore-pack"))}))
'''


def probe():
    """What's on the Deck: EmuDeck folders, free space, ES-DE media folder, RetroArch and the shader packs.
    Returns (dict, error text)."""
    try:
        r = ssh("python3 -", PROBE.encode(), timeout=60)
    except Exception as e:
        return None, str(e)
    if r.returncode != 0:
        return None, (r.stderr.decode("utf-8", "replace").strip() or f"ssh exit {r.returncode}")[-400:]
    try:
        info = json.loads(r.stdout.decode("utf-8", "replace").strip().splitlines()[-1])
    except Exception as e:
        return None, f"unexpected reply from the Deck: {e}"
    if DECK.get("roms"):
        info["roms"] = DECK["roms"]
    if DECK.get("media"):
        info["media"] = DECK["media"]
    return info, ""


def save_deck(**kw):
    """Write keys into the steam_deck section of lb_settings.json."""
    p = os.path.join(HERE, "lb_settings.json")
    s = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    s.setdefault("steam_deck", {}).update(kw)
    json.dump(s, open(p, "w", encoding="utf-8"), indent=2)
    DECK.update(kw)
