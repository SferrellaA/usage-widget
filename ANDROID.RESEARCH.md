# Android home-screen widget: research

Checked 2026-11-07. Investigation only. Nothing was built, installed, or signed in.

This note is about a home-screen widget for the same number this repo shows: SuperGrok weekly pool used, plus time until that window resets. It is not about a phone port of the Omarchy bar, and it is not about xAI API spend. Those are different quotas. The bar only needs `percentUsed` and `resetsAt`.

## Short answer

The label itself is a normal Android home-screen widget. A phone cannot run this repo. `BarWidget.qml` is an Omarchy/Quickshell plugin, and `bin/usage-collect` depends on a signed-in `grok` CLI on that Linux machine. Android apps cannot read another app's login, and there is no `~/.grok/auth.json` on a phone.

The missing piece is a permitted way to read the consumer weekly pool. Documented xAI billing is API and console spend, which this project already treats as a different number. SpaceXSI's acceptable use policy forbids unauthorized automated access. Publishing a client that polls an undocumented session is a different risk from running the official CLI on your own desktop.

Several third-party Play apps already put AI quotas, including Grok, on a home screen. The official Grok app has an in-app Usage tab. I found no evidence that the official app ships a home-screen usage widget.

Do not start an Android port until the data source is an official API, an official widget, or an explicit decision to accept the terms risk of an unofficial session. Copying a CLI token onto a phone is not that decision, and it breaks this repo's auth rules.

## What would have to be reimplemented

| Desktop piece | On Android |
| --- | --- |
| `BarWidget.qml` | Not portable. A widget is a `GlanceAppWidget` (or older `RemoteViews`) plus a receiver declared in the manifest. The launcher draws a snapshot the app pushes. |
| `usage_widget/display.py` and `Format.js` | Portable. Percent half-up, 0–100, joiner ` · `, `3d 4h` / `4h 12m` / `0h 42m`. `tests/vectors.json` can stay the contract. |
| `usage_widget/billing.py` | Not portable. It prefers the `grok` binary, then an in-memory CLI access token sent only to `cli-chat-proxy.grok.com`. A phone has neither the binary nor that session file. |
| `~/.local/state/usage-widget/status.json` | App-private storage. Same allowlist idea: percent, reset time, plan, status. No token, email, or account id. |
| 5-minute collector, local countdown | Split these. The network refresh cannot be a 5-minute shell timer. The countdown can still be derived from `resetsAt` without a network call. See below. |
| Click opens `grok login` | No CLI. Sign-in has to be something the phone can do, or the label stays `sign in`. |
| Official logomark SVG | Usable only under the brand rules below. Do not recolor it. Do not make it the Play icon. |

States worth keeping if a port ever happens: `…` before the first good read, `sign in` when the session is missing, `usage?` when billing failed and there is no current window, and drop the old percent once `resetsAt` has passed. Do not sum product rows. A missing `creditUsagePercent` on a new window is 0%, not a reset of a window that already had a reading.

## The widget UI is the easy part

Android home-screen widgets are app widgets. The user long-presses the home screen, picks Widgets, and places one. The app does not draw live UI in its own process. It publishes a `RemoteViews` tree. [Jetpack Glance](https://developer.android.com/develop/ui/compose/glance) is the current way to build that tree with Kotlin. It is not normal Compose: Glance composables are not interchangeable with Compose UI, and the result is still limited by `RemoteViews`.

That limit is fine for this label. Text, a small image, a tap target, and a couple of sizes (a short chip, maybe a wider one with the plan name) are ordinary widget content. Canonical widget layouts are the right reference, not a custom canvas.

What does not carry over from the bar:

- `updatePeriodMillis` cannot be under 30 minutes. Google’s advanced-widget guide says to set it to 0 and schedule work yourself if you want a different cadence, and points at `WorkManager`. Periodic work is also deferred by Doze and App Standby. Fifteen minutes is the usual floor for periodic `WorkManager`, and it is not exact.
- A widget does not run code every minute just because it is on the home screen. The Omarchy label can tick locally because the shell is already alive. On Android, pushing a new remote view every minute for a countdown is the wrong tool: it wakes the app, and the system may delay it anyway.
- Glance has no built-in countdown. Public answers for a per-minute Glance timer end up wrapping a platform `Chronometer` in `AndroidRemoteViews`. `Chronometer` can count down (API 24+). That is the plausible way to keep `4h 12m` moving between billing refreshes. It still needs a refresh when the format flips (under a day, last hour) and when the window ends, so the label does not sit on `100% · 0h 0m`.
- Exact alarms can force those refreshes. They need a special permission, and they are a poor fit for a usage chip. A tap-to-refresh plus a coarse background refresh is the pattern Google describes.
- The widget is killed with the usual background limits. A failed refresh should keep the last good reading only while that reading’s reset time is still ahead, same as the bar.

So: a chip that looks like `61% · 4h 12m` is buildable. Matching the bar’s 5-minute network poll is not, and it is unnecessary if the countdown is computed on the widget from a stored timestamp.

There is also a newer Remote Compose widget path aimed at Android 17. Android’s own samples say it does not replace Glance, and Glance remains the compatible choice. Not relevant for a first version.

## Where the number would come from

This is the blocker.

On the desktop, the signed-in Grok CLI owns the session. This process prefers that CLI so it does not read the token. The HTTP fallback is a narrow, in-memory read of an access token, sent only to `cli-chat-proxy.grok.com`, with redirects off that host refused. API keys are ignored on purpose.

None of that exists on Android:

- The official Grok app (`ai.x.grok`) is a separate sandbox. A third-party widget cannot read its session.
- There is no supported “install the Grok CLI on Android and call `grok login`” path for a home-screen widget.
- Copying `auth.json` or a bearer token onto the phone would put a credential in a place this repo refuses to log, store, or paste. It also ties a desktop CLI session to a published or sideloaded client the CLI did not issue the token to. Do not do that.
- [docs.x.ai billing](https://docs.x.ai/console/billing) is prepaid API credits, invoices, and team spend. The management billing API stops the API when prepaid credits and the spending limit are gone. That is not `creditUsagePercent` for the SuperGrok pool. A port that uses an API key would show the wrong quota, which is the bug this repo already guards against.
- Consumer docs describe the weekly pool and tell people to read it in the app: Settings → Usage, with the reset time shown there. See the [Grok FAQ](https://docs.x.ai/grok/faq). That is a first-party screen, not a third-party API.
- I did not find a public consumer “read my weekly pool” API for outside clients.

The [acceptable use policy](https://x.ai/legal/acceptable-use-policy) (effective 2026-08-14) applies to consumers and developers. It forbids accessing the Service through unauthorized automated or non-human means, “whether through a bot, script, or otherwise,” and it forbids bots, reverse engineering the service, circumventing rate limits, and presenting something as SpaceXSI when it is not. A personal script on a desktop is already in a gray area. An Android app whose job is to poll billing for you, and especially one you ship to other people, is closer to the thing that policy names.

I am not a lawyer. The practical reading is: do not design the port around scraping grok.com, replaying a CLI token, or a private WebView session, and then hope a disclaimer covers it. Those are the techniques third-party quota apps appear to use. They are also how an account gets suspended, and how a Play listing gets removed.

A clean port waits on one of:

1. SpaceXSI ships a home-screen widget in the official app. Use that.
2. SpaceXSI documents a consumer usage API, or blesses a third-party client. Then the collector is a small authenticated GET, with the same public allowlist this repo already has.
3. You decide the widget is only a manual display: you type the percent, or it reads a file you exported yourself. That avoids their service, and it is also a worse product than opening the official Usage tab.

Until one of those is true, an Android “version of this widget” is a new unofficial client, not a port.

## What already exists

I did not install these apps or inspect their traffic. Store listings are the source. Download counts are the coarse Play brackets, not exact installs.

**Official Grok** (`ai.x.grok`). Chat, voice, image, and video. 100M+ downloads. The Play listing I read does not mention a home-screen widget. Grok’s own posts and the consumer FAQ point at an in-app Usage tab (Settings → Usage) for the shared weekly pool, reset time, and product rows. That is the supported phone UI. It is buried in the app, which is the gap a widget would fill.

**AI Quota** (`com.aiquota.mobile`), by 미니코드. Play listing, updated 2026-11-04, 1K+ downloads. Explicitly: “Grok usage — check weekly credit usage and reset time,” plus widgets and a status-bar notification. Also Claude, Codex, Cursor, Gemini, Copilot, and others. Says most usage data and WebView sessions stay on device, some OAuth (Antigravity) uses a Firebase function, and raw cookies, API keys, and HTML are not sent to the developer. Disclaims affiliation with xAI. Changelog mentions Grok sign-in reliability and Grok Bot weekly usage. This is the closest existing thing to this widget, bundled with nine other providers.

**Nowdex** (`org.randynamic.nowdex`). Updated 2026-11-06, 10+ downloads. Home-screen widgets for coding quotas, and the supported list includes Grok. On-device keys, no Nowdex account claimed. Free tier is one service; Pro is a one-time purchase for the rest. Broader and more commercial than this repo.

**UsageArc** (`com.usagewidget.usage_widget`). Updated 2026-08-18, 0+ downloads. Generic “connected AI services” dashboard and a compact widget. Credentials in device secure storage, requests from the device, no developer server claimed. The listing I read does not name Grok, so it may or may not speak this pool.

**Not Android.** This repo, and other Omarchy chips such as `codeChap/grok-super-usage`, are desktop bar plugins. `wernerong/ai-usage-widget` is a Windows floating widget that mentions Grok. None of them install onto a phone home screen.

I found no open-source Android project that is clearly this SuperGrok pool widget. Absence on the first page of search is not proof none exists.

If the goal is “see the number on my phone this week,” try the official Usage tab, and if a home-screen chip matters, try AI Quota before writing one. I cannot vouch for how those apps log in or whether their Grok figure is the shared pool rather than a product row.

## Using one yourself vs publishing one

### Personal install

Building an APK and installing it on your own phone does not require a Play Console account, the $25 fee, or the 12-tester rule. `adb install` is still the straightforward path. Google’s [developer verification guide](https://developer.android.com/developer-verification/guides) says the ADB workflow stays the same.

Sideloading is no longer “install any APK forever, everywhere”:

- From 2026-09-30, certified devices in Brazil, Indonesia, Singapore, and Thailand check developer verification for installs from participating stores (Play, Samsung, Xiaomi, and others listed on that page). This phone’s country is outside that first wave unless you are there.
- Google plans to extend verification to all apps on certified devices in 2027, including installs that did not come from those stores.
- A verified developer can distribute normally. A limited-distribution account is the hobbyist path: no identity document in the comparison table, install on up to 20 devices via an invitation. An unverified APK can still be sideloaded, through an “advanced flow” with extra friction. The overview page describes limited-distribution accounts as not requiring a government ID or a registration fee; confirm that on the console before relying on it.

Personal install does not answer the xAI terms question. An app only you run is still automated access if it polls their service without authorization. It does avoid Play impersonation review, trademark review by Google, and shipping your sign-in flow to strangers.

Maintenance is yours. An undocumented billing shape can change without notice. The desktop widget has the same problem, with a smaller blast radius.

### Publishing on Google Play

This is a real product launch, not a checkbox.

- [Play Console registration](https://support.google.com/googleplay/android-developer/answer/6112435?hl=en) is a one-time US$25 fee. You must be 18. Identity verification is required.
- A personal account created after 2023-11-13 cannot go to production until a closed test has at least 12 testers opted in for the preceding 14 days. That is [Play’s testing requirement](https://support.google.com/googleplay/android-developer/answer/14151465?hl=en), not a rumor. Internal testing does not count as that gate. Organization accounts differ.
- New apps and updates submitted after 2026-08-31 must target Android 16 (API 36), with exceptions that do not apply to a phone app. [Target API requirements](https://support.google.com/googleplay/android-developer/answer/11926878?hl=en).
- A privacy policy URL and a Data safety form are required once the app handles an account or a token, even if the token never leaves the device. “We don’t run a server” is not a waiver. Declare on-device credentials honestly. Do not add analytics just because the form exists.
- [Impersonation policy](https://support.google.com/googleplay/android-developer/answer/9888374?hl=en): do not imply the app is related to, authorized by, or the official app of someone it is not. Icons, titles, and in-app marks count. Copying the Grok logo as the launcher icon is the example they give for other brands.
- Play is a poor place to distribute a client whose only network feature is an undocumented login. Reviewers, and xAI, can take it down later. Account termination risk belongs in the listing only if you are willing to own it.
- You would be maintaining sign-in for other people’s SuperGrok accounts. That is a support and security burden this repo deliberately does not take: no OAuth client, no cookie scrape, no API key, no token in the widget.

Closed testing via Play, without production, is a middle path for friends. It still needs the $25 account and identity verification, and the app is still subject to policy. It does not make the data source official.

Distributing the APK from this git repo is publishing too, just without Google. The 2027 verification plan is aimed at that channel on certified devices. An MIT license already allows others to ship the code; it does not grant trademark rights, and it does not grant a right to xAI’s service.

## Name, logo, and affiliation

[Brand guidelines](https://x.ai/legal/brand-guidelines) (page dated 2026-02-14 when fetched; the guidelines text says 2025-02-14):

- Marks may be used only to refer accurately to SpaceXSI or Grok.
- Do not use the marks in an app title, domain, or product name that SpaceXSI did not make.
- Do not imply endorsement, approval, or sponsorship.
- Logos only as provided, unmodified. They can revoke permission.
- Goodwill belongs to them.

This repo already follows that for a desktop label: unmodified logomark, not under the MIT license (`assets/NOTICE`), and a written non-affiliation line. A home-screen chip can do the same *inside* the widget, as a reference to the service being measured.

An app titled “Grok Usage,” a package name starting with `ai.x` or `x.ai`, or a launcher icon that is the logomark, conflicts with those guidelines and with Play impersonation. Safer shape if it is ever published: a dull name that does not contain Grok, a generic icon, “SuperGrok” only in body text as the thing being measured, and the same non-affiliation sentence the README uses. Even that is nominative use, which they can still object to.

The logomark files in `assets/` must not be edited, and must not be relicensed as MIT if an Android tree copies them.

## What I would not do

- Port `billing.py` by embedding the CLI host, client id, or token format in an Android app. That is the unauthorized-client path, and it does not belong in a research spike either.
- Read or copy `~/.grok/auth.json` to test a phone build.
- Fork the official Grok app, or hook its process.
- Treat AI Quota’s existence as permission. A listing can be enforcement that has not happened yet.
- Add a Play listing “for awareness” or “until the official widget exists.” Publishing is the expensive, higher-risk fork of this idea.

## If you still want one later

Only after the data-source decision above.

1. Prefer the official app’s widget if they ship one. Stop.
2. Otherwise, a tiny Kotlin app, Glance widget, no extra providers. One percent, one reset time, the display rules in `tests/vectors.json`.
3. Network refresh on a coarse `WorkManager` interval and on tap. Countdown from `resetsAt` on the widget, not from a 5-minute poll.
4. Session handling only through a documented API. Public record stays an allowlist. Nothing in logcat that looks like a token.
5. Personal install first (`adb`, or limited distribution if 2027 rules have reached you). Play only if strangers are actually the point, and only under a non-Grok name with a privacy policy and the closed-test gate.
6. Keep it out of this repo’s Omarchy plugin. A phone app is a different project. This file can stay as the reason it was or was not started.

## Sources

- This repo: `README.md`, `AGENTS.md`, `usage_widget/billing.py`, `usage_widget/display.py`, `assets/NOTICE`.
- Widget model: [Create an app widget with Glance](https://developer.android.com/develop/ui/compose/glance/create-app-widget), [Jetpack Glance](https://developer.android.com/develop/ui/compose/glance), [Create an advanced widget](https://developer.android.com/develop/ui/views/appwidgets/advanced) (`updatePeriodMillis` minimum 30 minutes; `WorkManager` for other cadences).
- Countdown gap: [Glance countdown thread](https://stackoverflow.com/questions/78616654/implement-countdown-timer-in-glance-widget), [Chronometer-in-Glance thread](https://stackoverflow.com/questions/77534084/how-to-use-timer-in-the-glance-widget).
- Sideload rules: [Android developer verification](https://developer.android.com/developer-verification), [guide](https://developer.android.com/developer-verification/guides). Enforcement from 2026-09-30 in Brazil, Indonesia, Singapore, and Thailand for listed stores; global certified-device expansion planned for 2027. ADB unchanged. Limited distribution up to 20 devices.
- Play: [Get started with Play Console](https://support.google.com/googleplay/android-developer/answer/6112435?hl=en) (US$25, age 18, identity verification), [personal-account testing](https://support.google.com/googleplay/android-developer/answer/14151465?hl=en) (12 testers, 14 days), [target API](https://support.google.com/googleplay/android-developer/answer/11926878?hl=en) (API 36 from 2026-08-31), [impersonation](https://support.google.com/googleplay/android-developer/answer/9888374?hl=en).
- SpaceXSI: [brand guidelines](https://x.ai/legal/brand-guidelines), [acceptable use policy](https://x.ai/legal/acceptable-use-policy) (2026-08-14), [API billing](https://docs.x.ai/console/billing), [Grok FAQ](https://docs.x.ai/grok/faq).
- Store listings fetched 2026-11-07: [Grok](https://play.google.com/store/apps/details?id=ai.x.grok), [AI Quota](https://play.google.com/store/apps/details?id=com.aiquota.mobile), [Nowdex](https://play.google.com/store/apps/details?id=org.randynamic.nowdex), [UsageArc](https://play.google.com/store/apps/details?id=com.usagewidget.usage_widget).
