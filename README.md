# B4B_exploit

Vibe coded tool to give you the maximum amount of burn cards in Back 4 Blood.
Cards are still consumed normally; rerun the tool to refill them.

## Requirements

- Windows x86-64 and **64-bit x86-64 Python 3.10 or later**.
  [Download Python](https://www.python.org/downloads/windows/).
- Steam installation and an existing offline save.
- The supported game executable; the script checks compatibility automatically.
  Other builds, Epic, Game Pass, consoles, and native ARM64 Python are unsupported.

No additional Python packages are needed. Close the game before using the tool.

## Back up first

Wait for Steam Cloud to finish syncing, then paste this into File Explorer's
address bar:

```text
%USERPROFILE%\AppData\Local\Back4Blood\Steam\Saved\SaveGames
```

**Copy the entire `SaveGames` folder to a separate, dated backup folder outside
this repository.**
Include `PlayerProfileSettings.sav`, `steam_autocloud.vdf`,
`PlayerProfileSettings.json`, `PlayerSettingsGame.sav` where present, and all
other files/subfolders. The JSON export cannot replace the encrypted `.sav`.

The tool also backs up **only the profile file it modifies** before each write:

```text
SaveGames\B4B_exploit_backups\<timestamp>\PlayerProfileSettings.sav
```

Keep your separate complete backup. Steam Cloud and automatic backups on the
same drive cannot guarantee protection against every kind of data loss.

## Run

1. Download and extract the repository ZIP. Keep the package files together.
2. Open a terminal in the extracted folder and check without changing your save:

   ```powershell
   py -3 burn_cards.py
   ```

3. If the check passes, apply the refill:

   ```powershell
   py -3 burn_cards.py --apply
   ```

4. Launch the game, choose **Play Offline**, and check **Decks → Burn Cards**
   and your existing progress.

If `py` is unavailable, replace `py -3` with `python`. Alternatively, double-click
**`Auffuellen.cmd`** after making your backup; this applies the change directly.
The launcher and script messages are in English.

If the game is not detected, add `--game-dir "path\to\Back 4 Blood"`.
For a different save location, add `--save-dir "path\to\SaveGames"`.
Use `--help` for options. If the executable check fails, do not bypass it.

## Restore

Close the game and preserve a copy of your current `SaveGames` folder first.
Temporarily disable Steam Cloud for Back 4 Blood under **Steam → Library →
Back 4 Blood → Properties → General** while restoring.

- **Undo a refill:** copy `PlayerProfileSettings.sav` from the desired timestamped
  automatic backup into the main `SaveGames` folder, replacing that file.
- **Restore everything locally:** replace `SaveGames` with your complete manual
  backup. Avoid accidentally nesting it as `SaveGames\SaveGames`.

This rolls back progress to the backup's date. Use only your own account's backup.
Verify the result in **Play Offline** before re-enabling Cloud synchronization.
If Steam reports a conflict, keep the verified copy you intend to use.
[Steam Cloud help](https://help.steampowered.com/en/faqs/view/68d2-35ab-09a9-7678).

## Safety and privacy

Only `offlineData.consumables` in `PlayerProfileSettings.sav` is changed.
The script validates encryption and checks that other profile data remains intact.
It uses cryptographic routines from your own verified game executable inside its
own process, without injecting into the game or disabling anti-cheat protection.

No personal Steam ID, key, or save is included. Each user's key is derived locally
at runtime and is not logged or saved. The tool has no networking or telemetry;
complete erasure of intermediate data from memory or crash dumps is not guaranteed.

**Never upload saves, VDF files, backups, or memory dumps to GitHub.** `.gitignore`
does not protect manual uploads or already tracked files. Check your Git author
name and email separately before publishing commits.

## Development and license

Package files: `burn_cards.py`, `burn-cards.json`, `Auffuellen.cmd`,
`test_burn_cards.py`, `README.md`, `AGENTS.md`, `CLAUDE.md`, `.gitignore`, `LICENSE`.

See `AGENTS.md` for coding-assistant instructions; `CLAUDE.md` references it too.
Run the synthetic-data tests with `py -3 -B -m unittest -v`.

The original tool code is source-available under the
[PolyForm Noncommercial License 1.0.0](LICENSE). Use, modification, and sharing
must follow its permitted purposes, including its specified organization uses;
general commercial-use rights are not granted.

Unofficial project for offline single-player use. No game binaries are included.
Game rights remain with their owners. Cloud, online, and future-update
compatibility are not guaranteed.
