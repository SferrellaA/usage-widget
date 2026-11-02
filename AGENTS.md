# usage-widget

Omarchy bar plugin. SuperGrok weekly usage on the top bar. Public repo: no secrets, ever.

## Setup

Follow this when a person asks to set the widget up, including when they only pasted the git URL and said "set this up." Do not improvise a different install path.

This is an end-user Omarchy setup. Do not edit `/usr/share/omarchy`. Do not read, print, copy, or commit `~/.grok/auth.json`, tokens, emails, or account ids. Do not add an API key. Do not symlink a checkout into `~/.config/omarchy/plugins/`: Quickshell misses updates through that symlink. `omarchy plugin add` clones the repo itself.

Stop if `command -v omarchy` fails. This widget only runs on Omarchy. Do not try to install Omarchy.

### 1. Grok CLI

The widget reads the session the Grok CLI already holds. It does not log the user in by itself.

```bash
command -v grok || test -x "$HOME/.grok/bin/grok"
```

If that fails, install the official CLI and stop if the installer fails:

```bash
omarchy-default-agent --install grok
```

Signed in means `~/.grok/auth.json` exists and is mode `0600`. Check with `stat`, not by reading the file. If it is missing, open a terminal and let the person finish login there:

```bash
omarchy launch terminal grok login
```

Do not capture that terminal's output. Do not paste a token into a file or an environment variable. When they say login is done, check the file mode again, then go on.

### 2. Install the plugin

Use the git URL the person gave you. The plugin id is `usage.limits`, from `manifest.json`, not the GitHub repo name.

```bash
omarchy plugin add <git-url> --enable --yes
```

That clones into `~/.config/omarchy/plugins/usage.limits` and enables it. If that directory is already a checkout of this plugin, update it instead of adding it again:

```bash
omarchy plugin update usage.limits --yes
```

### 3. Place it

Put the label immediately left of the clock, with a 64px spacer between them. Use the bar commands. Do not hand-edit `shell.json` for this.

```bash
omarchy bar move usage.limits --section center --before omarchy.clock
omarchy bar put omarchy.spacer --section center --before omarchy.clock
```

Then set the size on that spacer only. `omarchy bar set omarchy.spacer` changes the first spacer it finds, which may be a different one. Read `~/.config/omarchy/shell.json`, find the center entry that sits directly before `omarchy.clock`, and set that index:

```bash
omarchy bar set omarchy.spacer size 64 --json --section center --index <n>
```

If the bar has no `omarchy.clock`, skip the spacer and leave the widget in the section `omarchy plugin add` chose. Say so.

### 4. Check

Run the collector from the installed plugin, not from a random checkout:

```bash
python3 "$HOME/.config/omarchy/plugins/usage.limits/bin/usage-collect"
```

A good record has `ok` true, a `percentUsed`, a `resetsAt`, and `auth` of `ok`. Quote those fields only. If the JSON contains a token, an email, or an account id, stop and treat that as a bug. Do not paste the raw record into chat.

If the command works but the bar still says `no grok` or `sign in`, restart the shell once so it picks up `PATH`:

```bash
omarchy restart shell
```

Do not restart it in a loop. The label should look like `61% · 4h 12m`, with the Grok mark to the left of the percentage. The countdown is `3d 4h` at a day or more, and `0h 42m` in the last hour.

## Layout

- `BarWidget.qml` paints the label. It must not read `~/.grok/auth.json` or any token.
- `Format.js` and `usage_widget/display.py` format the countdown. They stay in lockstep; `tests/vectors.json` is the contract.
- `usage_widget/billing.py` is the only code allowed to touch the Grok session.
- `bin/usage-collect` prints one secret-free JSON record and writes the same record to the state file.

Do not fork `omarchy.agents` to add a provider. That panel is a display for records another program writes, and a fork goes stale on the next Omarchy update. A new provider is another collector that emits the same public record. The bar only reads `percentUsed` and `resetsAt`.

## What the number is

`percentUsed` is the shared weekly pool, `creditUsagePercent` from Grok billing. It is not the Grok Build, Chat, or Voice slice. Those product rows are a split of the same pool. Do not draw a missing product as 0%. If billing omits `creditUsagePercent`, the record is not ok. Do not invent a percent from local session files.

The bar label is `sign in` when the CLI session is missing, `no grok` when the binary is missing, `usage?` when billing failed and there is no last good reading, and `…` before the first fetch. A failed refresh keeps the last good percent on screen.

## Display

Percent is amount used, rounded half up, clamped to 0–100.

- `>= 1d`: `3d 4h`, always with an hour part (`1d 0h`, not `1d`).
- `< 1d`: `4h 12m`. The last hour is `0h 42m`. Under a minute is `0h 0m`.
- Joiner is ` · `, as in `59% · 3d 4h`.
- The mark left of the percentage is the official Grok logomark from the SpaceXSI brand kit, stored byte-for-byte. Do not recolor or edit those SVG files. Pick `Grok_Logomark_Light.svg` or `Grok_Logomark_Dark.svg` so the published fill stays visible.

The last hour also marks the label urgent, as does 90% or more used.

## Auth

Do not add an OAuth client, an API-key setting, or a browser-cookie scrape. `grok login` owns the session. Prefer the CLI billing call so this process does not read the token. The HTTP fallback may read the access token in memory only. It must not log it, write it, or follow a redirect off `cli-chat-proxy.grok.com`. Do not fall back to `XAI_API_KEY`.

Public records are an allowlist (`PUBLIC_KEYS`). A new field has to be added there on purpose. Never put email, user id, token, or raw billing JSON on stdout, in the state file, or in an error string.

## Checks

```bash
python3 -m unittest discover -s tests
omarchy plugin validate .
```

A live `python3 bin/usage-collect` is fine on a machine that is already signed in. Inspect the JSON before quoting it. If it contains anything that looks like a token or an email, that is a bug, not sample output.
