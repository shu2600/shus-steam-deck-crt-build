"""Give the Steam Deck the same TV / monitor / handheld looks as your PC build, in their lighter Mega Bezel STANDARD
versions (the Deck's 800p screen and battery do not need ADVANCED).

1. Shader packs: anything missing on the Deck (Mega Bezel, Duimon, TheNamec) is downloaded BY THE DECK from the same
   official pages the PC wizard uses, and unpacked into the RetroArch flatpak's shaders folder.
2. Looks: for every core your PC build set a look for (RetroArch\\config\\<Core>\\<Core>.slangp, including the looks you
   picked in the wizard), the Deck gets the STANDARD twin of that look, as a core preset and as the content-folder preset
   EmuDeck uses (config/<Core>/<roms folder>.slangp, which wins over the core preset). Old presets kept as .bak_emudeck.
Usage: py -I deck_looks.py [--dry]"""
import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deck_common as D  # noqa: E402

PACKS = [  # (probe key, url, folder under shaders, rename top folder to)
    ("mega_bezel", "https://buildbot.libretro.com/assets/frontend/shaders_slang.zip", "shaders_slang", None),
    ("duimon", "https://github.com/Duimon/Duimon-Mega-Bezel/releases/download/v1.1.7.0/Duimon-Mega-Bezel_v1.1.7.0.zip",
     "Mega_Bezel_Packs", None),
    ("thenamec", "https://github.com/TheNamec/megabezel-commodore-pack/archive/refs/heads/main.zip",
     "Mega_Bezel_Packs", "thenamec-commodore-pack"),
]
# RetroArch core folder -> the EmuDeck roms folders it plays
CORE_FOLDERS = {
    "Stella": ["atari2600"], "a5200": ["atari5200"], "Atari800": ["atari5200"], "ProSystem": ["atari7800"],
    "Gearcoleco": ["colecovision"], "FreeIntv": ["intellivision"], "Fuse": ["zxspectrum"], "Virtual Jaguar": ["atarijaguar"],
    "Handy": ["atarilynx"], "hatari": ["atarist"], "Hatari": ["atarist"], "PUAE": ["amiga"], "vecx": ["vectrex"],
    "Beetle PCE": ["tg16", "pcengine"], "Beetle PCE Fast": ["tg16", "pcengine"], "Genesis Plus GX": ["megadrive", "genesis"],
    "PicoDrive": ["megadrive", "genesis", "sega32x"], "Snes9x": ["snes"], "Mupen64Plus-Next": ["n64"],
    "FinalBurn Neo": ["neogeo"], "Flycast": ["dreamcast"], "Beetle NeoPop": ["ngpc"], "melonDS": ["nds"],
    "Citra": ["3ds"], "PPSSPP": ["psp"],
    "Atari800": ["atari5200"], "blueMSX": ["colecovision"], "Beetle Lynx": ["atarilynx"], "bsnes-hd beta": ["snes"],
}
ALIAS = {"Atari800": "a5200", "blueMSX": "Gearcoleco", "Beetle Lynx": "Handy", "bsnes-hd beta": "Snes9x"}   # other cores EmuDeck may pick: same look
DOWNLOAD = r'''
import os, sys, json, zipfile, urllib.request
url, dest, rename = json.loads(sys.stdin.read())
os.makedirs(dest, exist_ok=True); tmp = os.path.join(dest, "_download.zip")
with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "deck-crt-build"}), timeout=60) as r, open(tmp, "wb") as f:
    got = 0
    while True:
        b = r.read(1 << 22)
        if not b: break
        f.write(b); got += len(b); print(f"  {got >> 20} MB", flush=True)
root = os.path.realpath(dest)
with zipfile.ZipFile(tmp) as z:
    names = z.namelist(); top = names[0].split("/")[0] if rename else None
    for n in names:
        out = rename + n[len(top):] if rename and n.split("/")[0] == top else n
        t = os.path.realpath(os.path.join(dest, out))
        if not t.startswith(root + os.sep): continue
        if n.endswith("/"): os.makedirs(t, exist_ok=True); continue
        os.makedirs(os.path.dirname(t), exist_ok=True)
        with z.open(n) as s, open(t, "wb") as d: d.write(s.read())
os.remove(tmp); print("  unpacked", flush=True)
'''


def light(ref):
    """STANDARD twin of an ADVANCED preset path (same rules as the PC wizard's Light mode)."""
    cands = []
    if "/Presets/Advanced/" in ref or "[ADV]" in ref:
        std = ref.replace("/Presets/Advanced/", "/Presets/Standard/").replace("[ADV]", "[STD]")
        cands += [re.sub(r"-\[S\d+\]", "", std)]
    for heavy in ("MBZ_SHARP_ADV", "MBZ_SHARP_SMOOTH", "NMC_SHARP_SMOOTH-SCALEFX"):
        if heavy in ref:
            cands.append(ref.replace(heavy, "MBZ_SHARP_STD"))
    m = re.search(r"MBZ__\d__[A-Z0-9-]*ADV[A-Z0-9-]*__([A-Z-]+)\.slangp", ref)
    if m:
        cands.append(ref[:m.start()] + f"MBZ__3__STD__{m.group(1)}.slangp")
    return cands[0] if cands else ref


def pc_looks():
    """{core folder: (shaders-relative STANDARD preset, extra lines)} from the PC build's RetroArch core presets."""
    cfg = os.path.join(D.C.RA_DIR, "config"); sh = os.path.join(D.C.RA_DIR, "shaders"); out = {}
    for core in CORE_FOLDERS:
        p = os.path.join(cfg, core, core + ".slangp")
        if not os.path.exists(p):
            continue
        lines = open(p, encoding="utf-8").read().splitlines()
        ref = next((l.split('"')[1] for l in lines if l.startswith("#reference")), None)
        if not ref:
            continue
        rel = os.path.relpath(os.path.normpath(os.path.join(os.path.dirname(p), ref)), sh).replace("\\", "/")
        if rel.startswith(".."):
            continue
        extra = [l.replace('"../../shaders/', f'"{D.RA}/shaders/') for l in lines   # full Deck paths, as the hand-made presets had
                 if not l.startswith("#reference") and l.strip() and ":/" not in l and ":\\" not in l]
        out[core] = (light(rel), extra)
    for alt, src in ALIAS.items():
        if alt not in out and src in out:
            out[alt] = out[src]
    return out


def main(dry=False):
    info, err = D.probe()
    if not info:
        print("Can't reach the Deck:", err); return 1
    if not info.get("retroarch"):
        print("RetroArch (flatpak) isn't set up on the Deck yet: install EmuDeck and open RetroArch once."); return 1
    for key, url, sub, rename in PACKS:
        if info.get(key):
            print(f"{key}: already on the Deck"); continue
        print(f"{key}: the Deck is downloading it from {url.split('/')[2]}", flush=True)
        if not dry:
            r = D.ssh("python3 -c " + json.dumps(DOWNLOAD).replace("$", "\\$"), json.dumps([url, f"{D.RA}/shaders/{sub}", rename]).encode(), timeout=7200)
            print(r.stdout.decode("utf-8", "replace")[-300:], r.stderr.decode("utf-8", "replace")[-300:], flush=True)
    looks = pc_looks()
    script = ["set -e"]
    for core, (rel, extra) in looks.items():
        body = "\n".join([f'#reference "{D.RA}/shaders/{rel}"', 'HSM_INTRO_WHEN_TO_SHOW = "0.000000"'] + extra) + "\n"
        d = f"{D.RA}/config/{core}"
        for name in [core] + CORE_FOLDERS[core]:
            f = f"{d}/{name}.slangp"
            script.append(f'mkdir -p "{d}"; [ -f "{f}" ] && [ ! -f "{f}.bak_emudeck" ] && cp "{f}" "{f}.bak_emudeck" || true')
            script.append(f"cat > \"{f}\" <<'EOF_PRESET'\n{body}EOF_PRESET")
        cfgf = f"{d}/{core}.cfg"   # Mega Bezel draws its own frame: aspect = Full
        script.append(f'touch "{cfgf}"; grep -q "^aspect_ratio_index" "{cfgf}" && sed -i "s/^aspect_ratio_index.*/aspect_ratio_index = \\"24\\"/" "{cfgf}" || echo \'aspect_ratio_index = "24"\' >> "{cfgf}"')
        print(f"  {core}: {rel.split('/')[-1]}")
    if dry:
        print("\n".join(script)[:2000]); return 0
    r = D.ssh("bash -s", ("\n".join(script) + "\necho looks-done\n").encode())
    print(r.stdout.decode("utf-8", "replace")[-200:], r.stderr.decode("utf-8", "replace")[-400:])
    return 0 if b"looks-done" in r.stdout else 1


if __name__ == "__main__":
    sys.exit(main("--dry" in sys.argv))
