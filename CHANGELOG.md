# Changelog

## 0.1.0 (unreleased)

- Session: the integration now works from `SHARED_SESSION_DRUPAL`, the cookie Ten'Up
  uses to bridge its front end and its reservation area. It is not `HttpOnly`, so a
  bookmarklet can read it and the developer tools are no longer needed, and it lives
  about two months instead of the twenty three days of the Drupal session. Home
  Assistant opens a session from it whenever it needs one. A setup pasted before this
  keeps working on its `SESS` cookie.
- Setup: every step that asks for a session is now three numbered steps: a link that
  opens Ten'Up to log in, the bookmarklet that copies the session, and the field to
  paste it in.
- Setup: every step that asks for a session now opens with a link to Ten'Up and a
  reminder to be logged in there first, and the bookmarklet copies the session to the
  clipboard instead of showing it.
- Setup: the config entry can be reconfigured to hand over a new session, without
  waiting for the old one to expire.
- Session: when Ten'Up hands out a new session id while the integration is running,
  the new cookie is saved to the config entry. A restart no longer falls back to the
  value that was pasted at setup, and no longer asks to sign in again for a session
  that never expired.
- Session: the cookie field accepts a whole "Copy as cURL" paste from the browser Network
  tab. Only the Drupal session cookie is extracted, every other cookie, header and URL in
  the paste is ignored and never stored. Pasting the bare value still works.
- First version: club search, session cookie, planning of the coming days, sensors, calendar, book and cancel services, `tenup/planning` websocket command.
