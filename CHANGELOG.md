# Changelog

## 2.0.6

### The "Copy as cURL" shortcut is no longer suggested

It was offered as the easier of the two ways to hand over a session. It is not:
the Network tab lists every request a page makes, most of them to other sites
that carry nothing useful, so picking a row means knowing which one. That is
harder than reading a row in a table, not easier.

The dialogs and both READMEs now describe one way only, the Cookies view, with
the picture of the row to copy. Pasting a cURL still works for anyone who
prefers it; it is simply no longer presented as the simple path.

## 2.0.5

### A pasted session no longer inherits the refusals of the dead one

The integration asks for a new cookie only once Ten'Up has refused twice in a
row, so that a single hiccup never costs the user a trip to the dialog. That
count deliberately outlives the coordinator, which rebuilds on every setup
retry, but it also outlived the cookie it was counted against: a session just
validated started at two, and the first stumble sent the user straight back to
where they came from.

Validating a session now clears the count, which is sound because the flow has
just proved that session works.

## 2.0.4

### The dialog now shows which row to copy

Both session cookies are plain UUIDs sitting next to each other, and a browser
that lived through the rebuild still carries the old one. Nothing in the values
tells them apart, so the dialog now carries the picture: the row to take in
green, the one to leave struck through in red.

The screenshots are drawn, not captured: every value in them is a row of dots,
so no session of anyone's is in this repository.

## 2.0.3

### A pasted session now takes effect without reloading by hand

Since 1.2.0 the update listener owns every reload of the entry, which keeps a
reauth from being reloaded twice. But that listener is registered at the end of
a successful setup: an entry that never got that far has none, so a freshly
pasted session was written and then sat there doing nothing. That is exactly the
entry a user is most likely to be reauthenticating, and the only way out was a
restart of Home Assistant.

The flow now wakes an entry that is not loaded, and still leaves a loaded one to
its listener, which is the race Home Assistant raises on from 2026.12.

## 2.0.2

### Pasting a whole "Copy as cURL" now sends every cookie

Only the session cookie was pulled out of a paste and sent on. If Ten'Up wants a
companion cookie alongside it, that narrowing is what keeps the session from
being accepted, and the user has no way to tell.

The whole cookie set of a "Copy as cURL" or a "Cookie:" header is now kept as a
last candidate, tried after the session cookie on its own. Nothing more is asked
of the user: they have already handed the lot over.

Each API answer is also traced at debug level, with its status and the host that
answered, so a refusal can be told from a waiting room without guessing. No
value is ever logged.

## 2.0.1

### The session cookie changed name, and became HttpOnly

2.0.0 could reach the new API but never authenticate: the rebuild moved the back
end from Drupal to Java and renamed its session cookie with it. The site's own
code names `SHARED_SESSION_JAVA`, and no longer mentions the Drupal one at all.
A browser that lived through the migration still carries the old cookie, which
is exactly what made the failure confusing: the bookmarklet kept handing over a
perfectly fresh value that Ten'Up no longer accepts.

The integration now reads and sends the new cookie, and still accepts the old
ones so an installation made before the rebuild loads and says the session is
dead rather than that the cookie is malformed.

### The bookmarklet is gone

The new cookie is `HttpOnly`: no page script can read it, so no bookmarklet can
hand it over. The install page it was served from is removed rather than left
teaching a method that cannot work.

The session is now copied from the browser's developer tools, Cookies view, or
by pasting a whole "Copy as cURL" from the Network tab, which the integration
has always known how to read.

## 2.0.0

### Ten'Up rebuilt its member area, and this follows it

The FFT replaced the Drupal site with a new one on 13 October 2026, overnight.
Every address the integration used answers 404, the reservation grid is no
longer HTML to read, and the day no longer travels in the URL. Nothing short of
a new client could keep working.

It now speaks to the JSON API the new site uses, which is both sturdier and
plainer: one call returns a day of courts with their slots, who booked them and
whether the booking can still be cancelled. The HTML parser is gone, and with it
the whole business of reading a page meant for a browser.

Nothing changes for you. The cookie kept its name, so the bookmarklet still
works and an existing setup carries on without being touched. The card, the
sensors, the calendar, the services and the friends list are unchanged.

### A booking may never cost you anything

Ten'Up offers a slot through several "offers": a subscription, a ticket book, or
a ticket bought online. Only the subscription is free, and the integration now
refuses to book with anything else, for you and for the partner you name.

The old guard looked at the announced price, which no longer tells them apart:
the new API quotes the club's ticket rate on the subscription as well. It is the
kind of offer that decides now, never the figure next to it.

### The card shows your next booking

A band above the grid says when you play next, which court, and opens that day
when tapped. It covers every day Ten'Up returned, not only the days the grid
shows, and it ignores the court filter: it is your booking, wherever it is. Turn
it off with "Show your next booking above the grid" in the card editor.

### Verification

134 Python tests and 214 card assertions. The whole path was walked against the
real site, booked and cancelled: a court for one player, a court for two with a
club member named by hand, and the cancellation of both.

## 1.2.0

### The entry reloads itself, once

Reauthenticating or reconfiguring used to reload the entry twice: once from the
config flow, once from the integration's own update listener. Home Assistant
logs that as a deprecation and will raise on it from 2026.12
([core#169198](https://github.com/home-assistant/core/pull/169198)).

The flow now uses the non-reloading variant and the listener owns every reload,
which it has to: it is also what takes a new friend from the card without
refetching the whole horizon, and what absorbs a cookie Ten'Up rotates on its
own. A cookie the integration did not write itself is the mark of a reauth or a
reconfigure, and that one does get a reload.

**This raises the minimum to Home Assistant 2025.3**, which is where
`async_update_and_abort` was added.

### Verification

134 integration tests (127 before), covering both halves of the contract: the
flow schedules no reload of its own, and the listener reloads what it cannot
absorb. Mutants of each killed.

## 1.1.0

### The card ships with the integration

Ten'Up Card is no longer a separate download. The integration serves it and keeps one
Lovelace resource pointing at it, versioned with the integration, so the two can never
end up a release apart.

- Nothing to add by hand: no custom repository for the card, no dashboard resource.
- Coming from 1.0.x: remove **Ten'Up Card** from HACS. The integration drops the old
  resource on the next restart, and your cards keep their configuration. Until then
  both copies would fight over the same custom elements, so the bundle now refuses to
  register twice and the first one loaded wins.
- Lovelace resources declared in YAML are never written to. The integration logs the
  line to add instead.

### An expired cookie no longer leaks an HTTP session on every retry

Setting up an entry opens a dedicated aiohttp session, which was closed only when the
setup failed with one of the integration's own connection errors. The coordinator turns
those into `UpdateFailed`, which Home Assistant re-raises as `ConfigEntryNotReady`, so
that branch was never taken: every failed attempt left a session and a connector behind.
With a dead cookie the setup is retried about every ten minutes, for ever. Seen in
production on 2026-09-24, after some forty hours of `Unclosed client session` warnings.

Every way out of the setup now closes the session, including a shutdown mid-setup.

### An expired cookie now asks for a new one instead of retrying for ever

One refusal from Ten'Up is not proof, so the integration waits for a second one in a
row before asking for a new cookie. That counter lived on the coordinator, which a
failed setup throws away and rebuilds on every retry: it restarted at zero, never
reached two, and the entry stayed in `setup_retry` indefinitely instead of offering to
re-authenticate. It now lives with the config entry and survives the retries.

A waiting room or a bot challenge still never counts as an expired cookie, and a day
that works again clears the count.

### Verification

127 integration tests (99 before) and 208 card assertions (202 before), with the
mutants of each fix killed. Both suites now run in CI.

## 1.0.1

- A cancellation that Ten'Up accepted no longer reports an error. The answer page is
  not a normal session page and was read as a failure. The result is now judged on the
  planning: confirmed when the slot is no longer yours, an error only when it still is.
- A failed cancellation refreshes the grid at once instead of waiting up to fifteen
  minutes, and a cancellation that could not be verified says so.

## 1.0.0

First stable release.

- **Two-player booking.** `tenup.book` takes a `partner` field with a plain name. The
  integration searches the club members, refuses to choose between namesakes and asks
  for the first name, then picks a formula that costs nothing. A paid option is never
  selected: the single-ticket formula is ruled out in code, not merely hidden.
- New websocket command `tenup/partner/search`, used by the card so no member number is
  ever needed.
- The `tenup.probe_partner` diagnostic service of the pre-releases is gone.

## 0.4.2

Documentation only.

- README images use absolute addresses, so the logo and the cookie screenshot also show
  inside HACS, which does not rewrite relative paths in HTML image tags.
- Installation goes through the HACS 2 menus, says to search for `tenup`, and explains
  that a repository just added is listed as New and can be hidden by the status filter.

## 0.4.1

- Manifest keys put back in the order hassfest wants (`domain`, `name`, then
  alphabetical). 0.4.0 shipped `dependencies` before `name`, which fails validation.

## 0.4.0

First published release.

### Signing in without the developer tools

The integration now works from `SHARED_SESSION_DRUPAL`, the cookie Ten'Up uses to
bridge its front end and its reservation area. It is not `HttpOnly`, so a bookmarklet
can read it, and it lives about two months against the twenty three days of the Drupal
session. Home Assistant opens a session from it whenever it needs one.

- The session dialog reads as three steps: a link to your own club reservation grid,
  the bookmarklet that copies the session to the clipboard, and the field to paste it
  in. The bookmarklet line is shown in the dialog, ready to copy.
- Home Assistant serves an install page at `/api/tenup/bookmarklet`, where the
  bookmarklet can be dragged to the bookmarks bar. It is static documentation, holds
  no user data, and is offered in French or English depending on the browser.
- The bookmarklet only works from inside the reservation area, and both the dialog and
  the bookmarklet's own message say so.
- The field also accepts a whole "Copy as cURL" paste from the browser Network tab, or
  a bare cookie value. Only the useful cookie is kept: other cookies, headers and URLs
  are ignored and never stored.
- A setup made before this keeps working on its `SESS` cookie.

### Sessions

- A config entry can be reconfigured to hand over a new session, without waiting for
  the old one to expire.
- When Ten'Up replaces the session id while the integration is running, the new cookie
  is saved. A restart no longer falls back to the value pasted at setup, and no longer
  asks to sign in again for a session that never expired.

### The rest

Club search, planning of the coming days, sensors, calendar, `tenup.book` and
`tenup.cancel` services, and the `tenup/planning` websocket command for the companion
card.
