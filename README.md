# usage-widget

An [Omarchy](https://omarchy.org/) top-bar label for the weekly SuperGrok pool: how much is already used, and how long until that window resets.

```text
59% · 3d 4h
59% · 4h 12m
59% · 0h 42m
```

A day or more is days and hours (`1d 0h` when the hour part is zero). Under a day it is hours and minutes, so the last hour reads `0h 42m`. The mark to the left of the percentage is the official Grok logomark from the [SpaceXSI brand kit](https://x.ai/legal/brand-guidelines), copied unchanged so it can name the service this widget is reading. The light or dark file is chosen so it stays visible. Those files are not covered by the MIT license, and this project is not affiliated with or endorsed by SpaceXSI. The percentage is the shared weekly allowance, the same number grok.com shows, not a single product such as Grok Build.

Other inference providers are not wired up yet. The bar only needs a percent and a reset time, so a later provider can be another collector rather than a new widget.

## Install

An agent setting this up on another Omarchy machine should follow the Setup section in [AGENTS.md](AGENTS.md). That is the whole procedure.

By hand: sign in once with `grok login`, then:

```bash
omarchy plugin add <this-repo-url> --enable --yes
omarchy bar move usage.limits --section center --before omarchy.clock
```

A 64px `omarchy.spacer` belongs between the label and the clock. The Setup section says how to size that spacer without resizing a different one.

Left-click and right-click both refresh. If the CLI is missing or signed out, the label says `no grok` or `sign in`, and a click opens `grok login` in a terminal.

The reading refreshes every 15 minutes. The countdown ticks locally from the reset timestamp, so it does not call xAI every minute. Change the interval with:

```bash
omarchy bar set usage.limits refreshIntervalSec 900 --json
```

## What is stored

The widget never sees a credential. `bin/usage-collect` asks the signed-in `grok` CLI for billing. Only if that call fails does it read `~/.grok/auth.json` itself, and then only long enough to send the access token to `cli-chat-proxy.grok.com`. Redirects off that host are refused. API keys are ignored: they are a different quota.

The only file this writes is `~/.local/state/usage-widget/status.json`, mode `0600`. It contains the percent, reset time, plan label, and a short status. No token, email, or account id. None of that belongs in git.

## Develop

```bash
python3 -m unittest discover -s tests
python3 bin/usage-collect
omarchy plugin validate .
```

`usage-collect` prints one JSON object. Do not run it with debug flags that would echo HTTP headers.
