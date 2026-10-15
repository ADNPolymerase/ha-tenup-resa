<img src="https://raw.githubusercontent.com/ADNPolymerase/ha-tenup-resa/main/custom_components/tenup/brand/logo.png" alt="Ten'Up" width="420">

# Ten'Up for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/docs/faq/custom_repositories/)
[![GitHub Release](https://badgen.net/github/release/ADNPolymerase/ha-tenup-resa)](https://github.com/ADNPolymerase/ha-tenup-resa/releases)
[![Hassfest](https://github.com/ADNPolymerase/ha-tenup-resa/actions/workflows/hassfest.yml/badge.svg)](https://github.com/ADNPolymerase/ha-tenup-resa/actions/workflows/hassfest.yml)
[![HACS Action](https://github.com/ADNPolymerase/ha-tenup-resa/actions/workflows/hacs.yml/badge.svg)](https://github.com/ADNPolymerase/ha-tenup-resa/actions/workflows/hacs.yml)
[![Tests](https://github.com/ADNPolymerase/ha-tenup-resa/actions/workflows/tests.yml/badge.svg)](https://github.com/ADNPolymerase/ha-tenup-resa/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-support-yellow.svg?logo=buy-me-a-coffee)](https://buymeacoffee.com/adnpolymerase)

<a href="https://buymeacoffee.com/adnpolymerase" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-orange.png" alt="Buy Me A Coffee" height="60"></a>
<a href="https://adnpolymerase.github.io/HA/" target="_blank"><img src="https://raw.githubusercontent.com/ADNPolymerase/HA/main/assets/site-button.svg" alt="Link to my github.io for my other projects" height="60"></a>

See the free courts of your tennis club on [Ten'Up](https://tenup.fft.fr) (French Tennis Federation) and book or cancel a court from Home Assistant.

> 🇫🇷 [Lire en français](README.fr.md)

## What you get

- **Sensors**: free slots today, free slots over the coming days, next free slot, next reservation, number of reservations.
- **Calendar**: your reservations at the club.
- **Services**: `tenup.book` and `tenup.cancel`.
- **A Lovelace card**, shipped with the integration: the club grid, book and cancel in one tap.
- **Websocket command** `tenup/planning` with the full grid (courts x slots x days).

The integration reads the member reservation grid of your club (`Réserver dans mon club`), not the paid hourly rental.

## Requirements

- A Ten'Up account that is a member of the club (a licence with a booking formula).
- Home Assistant 2025.3 or newer.

## Installation

1. HACS > three dots > Custom repositories > `https://github.com/ADNPolymerase/ha-tenup-resa`, type Integration.
2. Search for `tenup` in HACS, download **Ten'Up**, restart Home Assistant.
3. Settings > Devices and services > Add integration > **Ten'Up**.

A repository you just added is listed as New and can be hidden by the status filter: search for it.

The card comes with it: there is nothing else to download and no Lovelace resource to add by hand.

> **Upgrading from 1.0.x?** The card used to live in its own repository. Remove **Ten'Up Card** from HACS: the integration serves its own copy and drops the old dashboard resource on the next restart. Your cards keep working, the configuration does not change.

## Configuration

1. **Your club**: type its name, pick it in the list (or paste its 8-digit Ten'Up code, visible in the URL of the reservation grid).
2. **Your session**: Ten'Up does not allow logging in with a password from a third-party tool (the login page is protected against automated logins), so the integration works with the session of your browser:
   **In the developer tools.** Sign in on tenup.fft.fr and open **"Book at my club"**. Press **F12** (⌥⌘I on a Mac), **Application** tab (**Storage** in Firefox), **Cookies** > `https://tenup.fft.fr`, and copy the value of the **`SHARED_SESSION_JAVA`** row:

   <img src="https://raw.githubusercontent.com/ADNPolymerase/ha-tenup-resa/main/custom_components/tenup/assets/cookie-devtools.png" alt="The session cookie row in the cookies" width="760">

   This cookie is `HttpOnly` since the October 2026 rebuild: no page script can read it, and the bookmarklet of earlier versions no longer works.

When the session expires, Home Assistant raises a repair asking for a fresh cookie. No password is ever stored.

Options: number of days to fetch (default 7, the club horizon) and refresh interval (default 15 minutes).

## The card

Add **Ten'Up Card** from the card picker, or:

```yaml
type: custom:ha-tenup-card
days: 3
```

- **The club grid**: one tab per day, courts in columns, slots at their real size.
- **Colours**: green free, yellow 2 players needed, red taken, purple a friend, blue yours, grey past.
- **Book and cancel** in one tap, after a confirmation.
- **2-player courts**: search your partner and book from the card. No member number to look up.
- **Visual editor**, English and French.

| Option | Default | |
|---|---|---|
| `name` | club name | Title |
| `entry_id` | first club | Club to show |
| `days` | `3` | Day tabs, 1 to 7 |
| `start_hour`, `end_hour` | club grid | Hours shown |
| `courts` | all | Courts shown |
| `next_booking` | `true` | Announce your next booking above the grid |
| `show_names` | `true` | Show who booked. Off: no names, no following from the grid |
| `confirm` | `true` | Ask before booking or cancelling |
| `compact` | `false` | Smaller cells |
| `language` | `auto` | `auto`, `en` or `fr` |

Cancelling is immediate on Ten'Up: keep `confirm` on.

### Friends

Their bookings turn purple. Tap a booking to follow a player by initial (just them) or with **Every NAME** (family and namesakes), or manage the list from the header button.

A partner you book with can be remembered from the booking dialog, and is then offered in one tap next time.

Ten'Up only shows the first-name initial in the grid, so two players sharing it and a surname are coloured alike. Booking is not affected: the partner you pick is identified exactly.

## Services

```yaml
service: tenup.book
data:
  court_id: "21100"          # see the attributes of the sensors or the planning command
  start: "2026-09-10 21:00:00"
  partner: "John DOE"   # only for a court that needs two players
```

```yaml
service: tenup.cancel
data:
  reservation_id: "123456789"   # or court_id + start
```

Both services return a response (`response_variable`) and raise a readable error when Ten'Up refuses (for example the club rule on simultaneous reservations).

Courts that require two players are bookable too. Pass `partner` with a name: the integration searches the club members, refuses to choose between namesakes and asks you to give the first name, then picks their subscription. A ticket book or a single ticket is never selected: only a subscription is free, and Ten'Up quotes the club's ticket rate on the subscription as well, so the kind of offer decides, never the figure next to it.

## Notes

- Ten'Up cancels a reservation without asking for confirmation. The service does exactly that, so wire a confirmation in your automations or dashboards.
- The public search API is used to find the club, everything else goes through your session.

## Support

Issues and ideas: [GitHub issues](https://github.com/ADNPolymerase/ha-tenup-resa/issues).

---

Ten'Up and the Ten'Up logo are trademarks of the Fédération Française de Tennis. This is an unofficial project, not affiliated with or endorsed by the FFT.
