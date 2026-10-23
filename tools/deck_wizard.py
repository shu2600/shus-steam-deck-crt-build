"""Shu's Steam Deck CRT Build - setup wizard (runs on your Windows PC, talks to the Deck over your home network).
Copies your LaunchBox games to EmuDeck on the Deck, gives every system the light version of the TV / monitor look your
PC build uses, brings the artwork across for ES-DE, and puts your favourites in Steam with box art.
Nothing here downloads, supplies or links to games or BIOS. Run with setup_deck.bat, or: py tools/deck_wizard.py"""
import ctypes, glob, json, os, queue, shutil, subprocess, sys, threading, webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

HERE = os.path.dirname(os.path.abspath(__file__))
SETTINGS = os.path.join(HERE, "lb_settings.json")
EXAMPLE = os.path.join(HERE, "lb_settings.example.json")
ASSETS = next((d for d in (os.path.join(os.path.dirname(HERE), "assets"),
                           os.path.join(os.path.dirname(os.path.dirname(HERE)), "release", "repo_docs", "assets")) if os.path.isdir(d)),
              os.path.join(os.path.dirname(HERE), "assets"))
PY = sys.executable
NAME = "Shu's Steam Deck CRT Build"
VERSION = "1.1"   # bump on every change and add a line to CHANGELOG.md
TITLE = NAME + " - Setup  (v" + VERSION + ")"
BG, PANEL, FG, MUTED, ACCENT, OK, BAD = "#14161a", "#1d2026", "#e9e6df", "#9a9a94", "#d9a441", "#7fbf6a", "#d0675b"
MODES = {"all": "All games", "playlists": "Playlist games only", "none": "Don't copy"}
NET_STEPS = ("1. Put the Deck on the same network as this PC\n"
             "   On the Deck: Steam button > Settings > Internet > pick the same Wi-Fi your PC uses.\n"
             "   Its address is on the same page: select your network, then look for IP Address (four numbers with dots).\n"
             "   Faster and steadier: a USB-C hub or dock with an Ethernet port, cable into your router.\n"
             "2. Keep it awake while copying\n"
             "   Plug the charger in, and set the sleep timer for when it's plugged in to Never for the copy\n"
             "   (Settings > Power; on older SteamOS it's under Settings > Display).")
SSH_STEPS = ("3. Let this PC talk to the Deck (one time)\n"
             "   On the Deck: hold the power button, pick Switch to Desktop, open Konsole and type:\n"
             "      passwd                          (choose a password for the deck user; you type it, nothing stores it)\n"
             "      sudo systemctl enable --now sshd\n"
             "   Then come back here, type the Deck's address above, press Set up the key, and type that password once\n"
             "   in the window that opens. Press Test connection.")


def load():
    for p in (SETTINGS, EXAMPLE):
        if os.path.exists(p):
            return json.load(open(p, encoding="utf-8"))
    return {}


def save(s):
    json.dump(s, open(SETTINGS, "w", encoding="utf-8"), indent=2)


def fresh_modules():
    for m in ("lbconfig", "deck_common", "deck_plan"):
        sys.modules.pop(m, None)
    sys.path.insert(0, HERE)
    import deck_common, deck_plan
    return deck_common, deck_plan


class Wizard(tk.Tk):
    def __init__(self):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
        super().__init__()
        self.title(TITLE); self.configure(bg=BG)
        k = self.ui = self.winfo_fpixels("1i") / 96.0
        self.geometry(f"{int(1100 * k)}x{int(800 * k)}"); self.minsize(int(900 * k), int(660 * k))
        self.s = load(); self.imgs = {}; self.info = None; self.cancelled = False; self.proc = None
        st = ttk.Style(self); st.theme_use("clam")
        st.configure(".", background=BG, foreground=FG, font=("Segoe UI", 11))
        st.configure("TFrame", background=BG); st.configure("TLabel", background=BG, foreground=FG)
        st.configure("Muted.TLabel", foreground=MUTED); st.configure("H.TLabel", font=("Segoe UI Semibold", 20), foreground=ACCENT)
        st.configure("TButton", padding=(18, 8), background=PANEL, foreground=FG, bordercolor="#3a3f48", focuscolor=PANEL)
        st.map("TButton", background=[("active", "#2a2f37"), ("disabled", BG)], foreground=[("disabled", "#555a61")])
        st.configure("Accent.TButton", background=ACCENT, foreground="#14161a", bordercolor=ACCENT)
        st.map("Accent.TButton", background=[("active", "#e8b65a")])
        st.configure("TEntry", fieldbackground=PANEL, foreground=FG, insertcolor=FG, bordercolor="#3a3f48")
        st.configure("TCheckbutton", background=BG, foreground=FG); st.configure("Horizontal.TProgressbar", background=ACCENT)
        st.configure("TCombobox", fieldbackground=PANEL, background=PANEL, foreground=FG, arrowcolor=FG, bordercolor="#3a3f48")
        st.map("TCombobox", fieldbackground=[("readonly", PANEL)], foreground=[("readonly", FG)],
               selectbackground=[("readonly", PANEL)], selectforeground=[("readonly", FG)], background=[("readonly", PANEL)])
        self.option_add("*TCombobox*Listbox.background", PANEL); self.option_add("*TCombobox*Listbox.foreground", FG)
        self.option_add("*TCombobox*Listbox.selectBackground", ACCENT); self.option_add("*TCombobox*Listbox.selectForeground", "#14161a")
        self.body = ttk.Frame(self, padding=24); self.body.pack(fill="both", expand=True)
        nav = ttk.Frame(self, padding=(24, 0, 24, 18)); nav.pack(fill="x")
        self.back = ttk.Button(nav, text="Back", command=lambda: self.go(-1)); self.back.pack(side="left")
        credit = ttk.Frame(nav); credit.pack(side="left", padx=30)
        for name, h in (("shu_logo.png", 30), ("anima_logo.png", 22)):
            im = self.logo(name, h)
            if im:
                tk.Label(credit, image=im, bg=BG).pack(side="left", padx=6)
        ttk.Label(credit, text="Built by Shu and Anima", style="Muted.TLabel").pack(side="left", padx=8)
        link = tk.Label(credit, text="shuhq.com", fg=ACCENT, bg=BG, cursor="hand2", font=("Segoe UI", 10, "underline"))
        link.pack(side="left"); link.bind("<Button-1>", lambda e: webbrowser.open("https://shuhq.com"))
        self.next = ttk.Button(nav, text="Next", style="Accent.TButton", command=lambda: self.go(1)); self.next.pack(side="right")
        self.step = ttk.Label(nav, style="Muted.TLabel"); self.step.pack(side="right", padx=16)
        self.pages = [self.p_welcome, self.p_pc, self.p_connect, self.p_games, self.p_extras, self.p_send, self.p_done]
        self.i = 0; self.show()

    # ---- helpers ----------------------------------------------------------------------------------------------
    def logo(self, name, height):
        key = (name, height)
        if key not in self.imgs:
            try:
                from PIL import Image, ImageTk
                im = Image.open(os.path.join(ASSETS, name)).convert("RGBA"); h = int(height * self.ui)
                self.imgs[key] = ImageTk.PhotoImage(im.resize((max(1, int(im.width * h / im.height)), h), Image.LANCZOS))
            except Exception:
                self.imgs[key] = None
        return self.imgs[key]

    def clear(self):
        for w in self.body.winfo_children():
            w.destroy()

    def header(self, title, sub):
        ttk.Label(self.body, text=title, style="H.TLabel").pack(anchor="w")
        ttk.Label(self.body, text=sub, style="Muted.TLabel", wraplength=int(1000 * self.ui), justify="left").pack(anchor="w", pady=(4, 14))

    def show(self):
        self.clear(); self.pages[self.i]()
        self.back.state(["!disabled"] if 0 < self.i < len(self.pages) - 1 else ["disabled"])
        self.next.configure(text="Finish" if self.i == len(self.pages) - 1 else "Next")
        self.step.configure(text=f"Step {self.i + 1} of {len(self.pages)}")

    def go(self, d):
        if d > 0:
            if self.i == 0 and not self.agree.get():
                messagebox.showwarning(TITLE, "Please tick the box to confirm you'll use your own games and BIOS files."); return
            if self.i == 1 and not self.save_pc():
                return
            if self.i == 2 and not self.info:
                if not messagebox.askyesno(TITLE, "The Deck hasn't answered yet. Carry on anyway? The send step needs it."):
                    return
            if self.i == 3:
                self.save_modes()
            if self.i == len(self.pages) - 1:
                self.destroy(); return
        self.i = max(0, min(len(self.pages) - 1, self.i + d)); self.show()

    # ---- 1 welcome ---------------------------------------------------------------------------------------------
    def p_welcome(self):
        k = self.ui
        try:
            from PIL import Image, ImageDraw, ImageFont, ImageTk
            src = Image.open(os.path.join(ASSETS, "welcome_tv.jpg")).convert("RGB")
            W, H = src.size; w, h = int(1100 * k) - 48, int(560 * k); cw = W * 0.79; ch = cw * h / w
            im = src.crop((int(W / 2 - cw / 2), int(max(0, H * 0.475 - ch / 2)), int(W / 2 + cw / 2), int(min(H, H * 0.475 + ch / 2)))).resize((w, h))
            bg = tuple(int(BG[i:i + 2], 16) for i in (1, 3, 5)); fade = Image.new("L", (1, h))
            for y in range(h):
                fade.putpixel((0, y), int(255 * min(1.0, max(0.0, (y / (h - 1) - 0.55) / 0.45) ** 1.4)))
            im = Image.composite(Image.new("RGB", im.size, bg), im, fade.resize(im.size)); d = ImageDraw.Draw(im)
            f = ImageFont.truetype(os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "segoeuib.ttf"), int(52 * k))
            first, gold = NAME[:NAME.index("CRT")], NAME[NAME.index("CRT"):]
            x, y = int(36 * k), h - int(76 * k)
            d.text((x, y), first, font=f, fill=(233, 230, 223)); d.text((x + d.textlength(first, font=f), y), gold, font=f, fill=(217, 164, 65))
            self.imgs["banner"] = ImageTk.PhotoImage(im)
            tk.Label(self.body, image=self.imgs["banner"], bg=BG, bd=0).pack(anchor="w")
        except Exception:
            ttk.Label(self.body, text=NAME, style="H.TLabel").pack(anchor="w")
        under = tk.Frame(self.body, bg=BG); under.pack(fill="x", padx=int(36 * k))
        tk.Label(under, text="Sends your LaunchBox games to EmuDeck on your Steam Deck, each system on the light version of its period TV.",
                 bg=BG, fg="#c9c4b8", font=("Segoe UI", 13), wraplength=int(980 * k), justify="left").pack(anchor="w", pady=(2, 14))
        self.agree = tk.BooleanVar(value=self.s.get("_agreed", False))
        tk.Checkbutton(under, variable=self.agree, bg=BG, fg=FG, selectcolor=PANEL, activebackground=BG, activeforeground=FG,
                       font=("Segoe UI", 11), text="I'll only use games and BIOS files I own and dumped myself, or that are legally free.").pack(anchor="w")
        tk.Label(under, text="You need: the PC build done first, EmuDeck installed on the Deck, and both on the same network.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(12, 0))

    # ---- 2 your PC ---------------------------------------------------------------------------------------------
    def p_pc(self):
        self.header("Your PC build", "Where your LaunchBox and RetroArch are. If you ran the PC wizard, press Use my PC settings "
                    "and pick its lb_settings.json (in the PC build's tools folder).")
        self.vars = {}
        grid = ttk.Frame(self.body); grid.pack(fill="x")
        for r, (key, label) in enumerate((("launchbox", "LaunchBox folder (has LaunchBox.exe)"), ("retroarch", "RetroArch folder (has retroarch.exe)"),
                                          ("emulation_root", "Emulation folder (holds your ROM folders)"))):
            ttk.Label(grid, text=label).grid(row=r, column=0, sticky="w", pady=6)
            v = tk.StringVar(value=self.s.get(key, "")); self.vars[key] = v
            ttk.Entry(grid, textvariable=v, width=70).grid(row=r, column=1, padx=8)
            ttk.Button(grid, text="Browse", command=lambda v=v: v.set(filedialog.askdirectory() or v.get())).grid(row=r, column=2)
        ttk.Button(self.body, text="Use my PC settings", command=self.import_pc).pack(anchor="w", pady=14)

    def import_pc(self):
        p = filedialog.askopenfilename(title="Your PC build's lb_settings.json", filetypes=[("Settings", "lb_settings.json"), ("JSON", "*.json")])
        if not p:
            return
        pc = json.load(open(p, encoding="utf-8"))
        for k in ("launchbox", "retroarch", "emulation_root", "mame", "work_dir", "rom_folders", "favourites"):
            if pc.get(k):
                self.s[k] = pc[k]
        for k, v in self.vars.items():
            v.set(self.s.get(k, ""))

    def save_pc(self):
        for k, v in self.vars.items():
            self.s[k] = v.get().strip()
        if not os.path.exists(os.path.join(self.s.get("launchbox", ""), "LaunchBox.exe")):
            messagebox.showwarning(TITLE, "Please set your LaunchBox folder."); return False
        save(self.s); return True

    # ---- 3 connect ---------------------------------------------------------------------------------------------
    def p_connect(self):
        self.header("Connect to the Deck", "The Deck and this PC need to be on the same network. Steam Deck's address is usually "
                    "steamdeck.local; if that doesn't answer, use its IP (Settings > Internet on the Deck).")
        row = ttk.Frame(self.body); row.pack(fill="x")
        ttk.Label(row, text="Deck address").pack(side="left")
        self.hostv = tk.StringVar(value=(self.s.get("steam_deck") or {}).get("host", "steamdeck.local"))
        ttk.Entry(row, textvariable=self.hostv, width=30).pack(side="left", padx=10)
        ttk.Button(row, text="Set up the key", command=self.setup_key).pack(side="left", padx=6)
        ttk.Button(row, text="Test connection", style="Accent.TButton", command=self.test).pack(side="left", padx=6)
        for text in (NET_STEPS, SSH_STEPS):
            tk.Label(self.body, text=text, bg=PANEL, fg=FG, font=("Consolas", 10), justify="left", anchor="w", padx=16, pady=12).pack(fill="x", pady=(14, 0))
        self.result = tk.Label(self.body, text="", bg=BG, fg=MUTED, font=("Segoe UI", 11), justify="left", wraplength=int(1000 * self.ui))
        self.result.pack(anchor="w")
        if self.info:
            self.show_info()

    def deck_host(self):
        h = self.hostv.get().strip() or "steamdeck.local"
        self.s.setdefault("steam_deck", {})["host"] = h; save(self.s)
        return h if "@" in h else "deck@" + h

    def setup_key(self):
        """Make an SSH key on this PC if there isn't one, then add it to the Deck. The Deck asks for its password in the
        console window; you type it there, the wizard never sees it."""
        h = self.deck_host(); key = os.path.expanduser(os.path.join("~", ".ssh", "id_ed25519"))
        os.makedirs(os.path.dirname(key), exist_ok=True)
        if not os.path.exists(key):
            subprocess.run(["ssh-keygen", "-t", "ed25519", "-N", "", "-f", key], capture_output=True)
        cmd = (f'type "{key}.pub" | ssh -o StrictHostKeyChecking=accept-new {h} '
               '"mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && echo KEY ADDED"'
               ' & echo. & echo You can close this window and press Test connection. & pause')
        subprocess.Popen(["cmd", "/c", cmd], creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))

    def test(self):
        self.deck_host(); self.result.configure(text="Asking the Deck...", fg=MUTED); self.update()

        def work():
            D, _ = fresh_modules()
            info, err = D.probe()
            self.after(0, lambda: self.on_probe(info, err))
        threading.Thread(target=work, daemon=True).start()

    def on_probe(self, info, err):
        self.info = info
        if not info:
            self.result.configure(fg=BAD, text="The Deck didn't answer: " + err + "\nCheck it's awake, on the same network, and that SSH and the key are set up.")
            return
        self.show_info()

    def show_info(self):
        i = self.info
        lines = [f"Connected. EmuDeck games folder: {i['roms'] or 'NOT FOUND (install EmuDeck on the Deck first)'}",
                 f"Free space there: {i['free'] / 1e9:.0f} GB",
                 f"ES-DE artwork folder: {i['media'] or 'not found'}",
                 "RetroArch: " + ("ready" if i["retroarch"] else "not set up (open RetroArch on the Deck once)"),
                 "Shader packs on the Deck: " + ", ".join(f"{n} {'yes' if i[k] else 'no (will be downloaded)'}" for n, k in
                                                         (("Mega Bezel", "mega_bezel"), ("Duimon", "duimon"), ("TheNamec", "thenamec")))]
        self.result.configure(fg=OK if i["roms"] else BAD, text="\n".join(lines))

    # ---- 4 games -----------------------------------------------------------------------------------------------
    def p_games(self):
        self.header("Which games", "Cartridge systems go over whole by default; disc systems only the games in your LaunchBox playlists. "
                    "Change any system, and keep the total under the Deck's free space.")
        self.total = ttk.Label(self.body, font=("Segoe UI Semibold", 12)); self.total.pack(anchor="w", pady=(0, 8))
        canvas = tk.Canvas(self.body, bg=BG, highlightthickness=0); sb = ttk.Scrollbar(self.body, command=canvas.yview)
        inner = ttk.Frame(canvas); inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw"); canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units") if canvas.winfo_exists() else None)
        _D, P = fresh_modules()
        self.P = P; self.games, self.listed = P.library(); self.sz = P.sizes(self.games, self.listed)
        saved = self.s.get("_deck_modes") or P.default_modes(self.games)
        self.modevars = {}
        for r, plat in enumerate(sorted(self.sz, key=lambda p: -self.sz[p][1])):
            n, b, pn, pb = self.sz[plat]
            ttk.Label(inner, text=plat).grid(row=r, column=0, sticky="w", pady=2, padx=(0, 18))
            v = tk.StringVar(value=MODES[saved.get(plat, "none")]); self.modevars[plat] = v
            cb = ttk.Combobox(inner, textvariable=v, values=list(MODES.values()), state="readonly", width=20); cb.grid(row=r, column=1)
            cb.bind("<<ComboboxSelected>>", lambda e: self.update_total())
            ttk.Label(inner, text=f"all {n} games {b / 1e9:.1f} GB   playlists {pn} games {pb / 1e9:.1f} GB", style="Muted.TLabel").grid(row=r, column=2, sticky="w", padx=16)
        self.update_total()

    def modes(self):
        back = {v: k for k, v in MODES.items()}
        return {p: back[v.get()] for p, v in getattr(self, "modevars", {}).items()}

    def update_total(self):
        tot = 0
        for p, m in self.modes().items():
            n, b, pn, pb = self.sz[p]
            tot += b if m == "all" else pb if m == "playlists" else 0
        free = self.info["free"] if self.info else None
        txt = f"Selected: {tot / 1e9:.1f} GB" + (f"   Free on the Deck: {free / 1e9:.0f} GB" if free else "")
        self.total.configure(text=txt, foreground=BAD if free and tot > free * 0.95 else FG)

    def save_modes(self):
        if hasattr(self, "modevars"):
            self.s["_deck_modes"] = self.modes(); save(self.s)

    # ---- 5 extras ----------------------------------------------------------------------------------------------
    def p_extras(self):
        self.header("Looks and extras", "What else to set up on the Deck besides copying the games.")
        self.opt = {}
        for key, text, default in (("looks", "TV and monitor looks: the light (Mega Bezel Standard) version of each look your PC build uses. "
                                             "Missing shader packs are downloaded by the Deck from their official pages.", True),
                                   ("art", "Artwork: LaunchBox covers, 3D boxes, logos and screenshots copied into ES-DE.", True),
                                   ("faves", "Steam favourites: your LaunchBox favourites added to Steam with box art. Steam closes for a "
                                             "moment while they're added; the old shortcuts file is kept as a backup.", True)):
            v = tk.BooleanVar(value=self.s.get("_deck_opts", {}).get(key, default)); self.opt[key] = v
            tk.Checkbutton(self.body, variable=v, text=text, bg=BG, fg=FG, selectcolor=PANEL, activebackground=BG, activeforeground=FG,
                           font=("Segoe UI", 11), wraplength=int(950 * self.ui), justify="left").pack(anchor="w", pady=8)

    # ---- 6 send ------------------------------------------------------------------------------------------------
    def p_send(self):
        if hasattr(self, "opt"):
            self.s["_deck_opts"] = {k: v.get() for k, v in self.opt.items()}; save(self.s)
        self.header("Send to the Deck", "Keep the Deck awake and on charge. Big collections take a while over wifi; Cancel stops it "
                    "and running it again carries on where it left off.")
        bar = ttk.Frame(self.body); bar.pack(fill="x")
        self.start = ttk.Button(bar, text="Start", style="Accent.TButton", command=self.run); self.start.pack(side="left")
        self.cancel_btn = ttk.Button(bar, text="Cancel", command=self.cancel); self.cancel_btn.pack(side="left", padx=10)
        self.cancel_btn.state(["disabled"])
        self.logbox = tk.Text(self.body, bg=PANEL, fg=FG, font=("Consolas", 10), wrap="word", relief="flat")
        self.logbox.pack(fill="both", expand=True, pady=(14, 0))
        self.q = queue.Queue(); self.after(150, self.pump)

    def log(self, line):
        self.q.put(line)

    def pump(self):
        try:
            while True:
                line = self.q.get_nowait()
                if self.logbox.winfo_exists():
                    self.logbox.insert("end", line + "\n"); self.logbox.see("end")
        except (queue.Empty, tk.TclError):
            pass
        if self.winfo_exists():
            self.after(150, self.pump)

    def call(self, args):
        self.proc = subprocess.Popen([PY, "-I", os.path.join(HERE, args[0])] + args[1:], cwd=HERE, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for line in self.proc.stdout:
            self.log("   " + line.rstrip())
        rc = self.proc.wait(); self.proc = None
        return rc

    def cancel(self):
        self.cancelled = True; self.cancel_btn.state(["disabled"]); self.log("\nCancelling...")
        if self.proc and self.proc.poll() is None:
            subprocess.run(["taskkill", "/PID", str(self.proc.pid), "/T", "/F"], capture_output=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

    def run(self):
        self.start.state(["disabled"]); self.cancel_btn.state(["!disabled"]); self.cancelled = False
        opts = self.s.get("_deck_opts", {"looks": True, "art": True, "faves": True})
        modes = self.s.get("_deck_modes")

        def done():
            self.after(0, lambda: (self.start.state(["!disabled"]), self.cancel_btn.state(["disabled"])) if self.start.winfo_exists() else None)

        def work():
            _D, P = fresh_modules()
            self.log("== Working out what to send")
            try:
                g, l = P.library()
                items = P.build(modes or P.default_modes(g), g, l); P.save(items)
            except Exception as e:
                self.log(f"   Couldn't read your LaunchBox library: {e}\n\nStopped. Nothing was sent."); done(); return
            self.log(f"   {len(items)} files, {sum(i['size'] for i in items) / 1e9:.1f} GB")
            for note in getattr(P, "NOTES", []):
                self.log("   " + note)
            steps = [("Copy the games", ["deck_copy.py"])]
            if opts.get("looks"):
                steps.append(("TV and monitor looks", ["deck_looks.py"]))
            if opts.get("art"):
                steps.append(("Artwork for ES-DE", ["deck_media.py"]))
            if opts.get("faves"):
                steps.append(("Steam favourites", ["deck_faves.py"]))
            failed = []
            for n, (label, cmd) in enumerate(steps, 1):
                if self.cancelled:
                    break
                self.log(f"\n== {n}/{len(steps)}  {label}")
                try:
                    rc = self.call(cmd)
                except Exception as e:
                    self.log(f"   couldn't start {cmd[0]}: {e}"); rc = -1
                if self.cancelled:
                    break
                if rc != 0:
                    failed.append(label); self.log(f"   ** {label} went wrong (exit {rc}). See the lines above.")
                    if cmd[0] == "deck_copy.py":    # the rest needs the games on the Deck
                        self.log("   Stopping here: the other steps need the games copied first."); break
            if self.cancelled:
                self.log("\nCancelled. Run it again to carry on.")
            elif failed:
                self.log(f"\nFinished with {len(failed)} problem(s): {', '.join(failed)}. Fix what's above and run it again; "
                         "anything already on the Deck is skipped.")
            else:
                self.log("\nAll done. On the Deck, open ES-DE or your Steam library.")
            done()
        threading.Thread(target=work, daemon=True).start()

    # ---- 7 done ------------------------------------------------------------------------------------------------
    def p_done(self):
        self.header("Finished", "On the Deck: Game Mode > Library > Non-Steam for your favourites, or open ES-DE for everything. "
                    "To change a look later, change it in the PC wizard and run this again.")


if __name__ == "__main__":
    Wizard().mainloop()
