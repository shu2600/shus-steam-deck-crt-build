# Shu's Steam Deck CRT Build

![The Steam Deck wizard's welcome screen](docs/screenshots/1_welcome.jpg)

Once my collection looked right on the big TV I wanted the same in my hands, so this is the Steam Deck side of [Shu's LaunchBox 4K CRT Build](https://github.com/shu2600/shus-launchbox-4k-crt-build). You run it on your Windows PC and it sends your LaunchBox games over your home network to EmuDeck on the Deck, every system on a lighter version of the same old TV, monitor or handheld look it gets on the PC.

**No games, BIOS or firmware are included, downloaded or linked. You bring your own.** See [DISCLAIMER.md](DISCLAIMER.md).

**Version 1.1** (23 October 2026). What's changed: [CHANGELOG.md](CHANGELOG.md)

## Before you start

- The PC build done (it gives the Deck its library, looks and artwork).
- [EmuDeck](https://www.emudeck.com/) installed on the Deck, with RetroArch opened once.
- The Deck and your PC on the same network: Wi-Fi works, a USB-C hub with Ethernet is faster.

## Quick start

1. Download this repo (green Code button, Download ZIP) and unzip it anywhere on your PC.
2. Double-click **`setup_deck.bat`**. If Python isn't on your PC it offers to install it.

| Step | What happens |
|---|---|
| Welcome | What this is, and a tick to confirm you'll use your own games and BIOS |
| Your PC build | Where your LaunchBox and RetroArch are, or point it at your PC build's settings |
| Connect to the Deck | How to put the Deck on your network, turn on SSH (you set the Deck password yourself), add a key and test |
| Which games | Every system with its size: all games, playlist games only, or none, against the Deck's free space |
| Looks and extras | TV looks (Mega Bezel Standard), ES-DE artwork, Steam favourites with box art |
| Send to the Deck | Copies everything with a live log. Cancel stops it; running it again carries on |
| Finished | Where to find it all on the Deck |

| Connect | Which games |
|---|---|
| ![Connect](docs/screenshots/3_connect.jpg) | ![Which games](docs/screenshots/4_games.jpg) |

## What it does on the Deck

- Games go into EmuDeck's roms folders, on the internal drive or the SD card, wherever EmuDeck put them.
- Missing shader packs (Mega Bezel, Duimon, TheNamec) are downloaded by the Deck itself from their official pages.
- Each system gets the Standard version of its PC look, as the core preset and the content-folder preset EmuDeck uses.
  Old presets are kept as `.bak_emudeck`.
- LaunchBox covers, 3D boxes, logos and screenshots go into ES-DE's media folder.
- Your LaunchBox favourites become Steam shortcuts with box art. It only changes the shortcuts it made itself, and the old shortcuts file is kept as a backup.
- Two different games with the same file name each get sent; the second goes in its own folder.

## How it's made

I built this with Anima, my own AI setup. It's a hive mind of AI agents that all share one brain, a memory I've been building for months. Anima writes and tests the code with me and can call a council of other AIs (ChatGPT, Gemini, Grok, DeepSeek and more) to pick holes in it, ChatGPT's review is where the v1.1 fixes came from. I steer it, check what it does and run it on my own Deck first... there's a lot more Anima can do, more on that soon.

## Legal

Same as the PC build: you supply the games and BIOS, every third-party pack comes from its creator, and nothing of
theirs is redistributed here. Credits are in the PC build's [CREDITS.md](https://github.com/shu2600/shus-launchbox-4k-crt-build/blob/main/CREDITS.md).

Built by Shu and Anima · [shuhq.com](https://shuhq.com) · [Support Me On Patreon](https://www.patreon.com/cw/Shu2600) · [Buy Me a Coffee](https://buymeacoffee.com/Shu2600)
