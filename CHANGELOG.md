# Changelog

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
