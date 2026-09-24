# Changelog

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
