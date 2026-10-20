"""Send the games in deck_sync_list.json to the Deck's EmuDeck roms folder as one tar stream over SSH.
Files already on the Deck with the same name and size are skipped, so it is safe to run again after a stop.
Usage: py -I deck_copy.py [roms folder on the Deck]   (default: found by deck_common.probe)"""
import json, os, sys, tarfile, time, subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import deck_common as D  # noqa: E402


def main(roms=None):
    if not roms:
        info, err = D.probe()
        if not info or not info.get("roms"):
            print("Can't find EmuDeck's roms folder on the Deck:", err or "is EmuDeck installed?"); return 1
        roms = info["roms"]
    items = json.load(open(os.path.join(D.HERE, "deck_sync_list.json"), encoding="utf-8"))
    have = {}
    r = D.ssh(f'cd "{roms}" && find . -type f -printf "%P\\t%s\\n"')
    for line in r.stdout.decode("utf-8", "replace").splitlines():
        if "\t" in line:
            p, s = line.rsplit("\t", 1); have[p.lower()] = int(s)
    todo = [it for it in items if have.get(it["dst"].lower()) != it["size"]]
    total = sum(it["size"] for it in todo)
    print(f"{len(todo)} files to send, {total / 1e9:.1f} GB ({len(items) - len(todo)} already on the Deck)", flush=True)
    if not todo:
        return 0
    proc = subprocess.Popen(D.ssh_args() + [f'cd "{roms}" && tar -xf -'], stdin=subprocess.PIPE,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    sent, t0 = 0, time.time()
    with tarfile.open(fileobj=proc.stdin, mode="w|") as tar:
        for i, it in enumerate(todo, 1):
            tar.add(it["src"], arcname=it["dst"], recursive=False)
            sent += it["size"]
            if i % 200 == 0 or it["size"] > 500e6 or i == len(todo):
                rate = sent / max(1, time.time() - t0) / 1e6
                print(f"{i}/{len(todo)}  {sent / 1e9:.1f}/{total / 1e9:.1f} GB  {rate:.0f} MB/s  {it['dst']}", flush=True)
    proc.stdin.close()
    rc = proc.wait()
    print(f"done ({'ok' if rc == 0 else 'exit ' + str(rc)}), {sent / 1e9:.1f} GB in {(time.time() - t0) / 60:.0f} min", flush=True)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else None))
