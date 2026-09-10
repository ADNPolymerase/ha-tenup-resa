# Ten'Up for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/docs/faq/custom_repositories/)
[![GitHub Release](https://badgen.net/github/release/ADNPolymerase/ha-tenup-resa)](https://github.com/ADNPolymerase/ha-tenup-resa/releases)
[![Hassfest](https://github.com/ADNPolymerase/ha-tenup-resa/actions/workflows/hassfest.yml/badge.svg)](https://github.com/ADNPolymerase/ha-tenup-resa/actions/workflows/hassfest.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

See the free courts of your tennis club on [Ten'Up](https://tenup.fft.fr) (French Tennis Federation) and book or cancel a court from Home Assistant.

> 🇫🇷 [Lire en français](README.fr.md)

## What you get

- **Sensors**: free slots today, free slots over the coming days, next free slot, next reservation, number of reservations.
- **Calendar**: your reservations at the club.
- **Services**: `tenup.book` and `tenup.cancel`.
- **Websocket command** `tenup/planning` with the full grid (courts x slots x days) for a companion card.

The integration reads the member reservation grid of your club (`Réserver dans mon club`), not the paid hourly rental.

## Requirements

- A Ten'Up account that is a member of the club (a licence with a booking formula).
- Home Assistant 2024.12 or newer.

## Installation

1. HACS > Integrations > three dots > Custom repositories > add `https://github.com/ADNPolymerase/ha-tenup-resa` (category Integration).
2. Install **Ten'Up**, restart Home Assistant.
3. Settings > Devices and services > Add integration > **Ten'Up**.

## Configuration

1. **Your club**: type its name, pick it in the list (or paste its 8-digit Ten'Up code, visible in the URL of the reservation grid).
2. **Your session**: Ten'Up does not allow logging in with a password from a third-party tool (the login page is protected against automated logins), so the integration works with the session of your browser:
   - log in on tenup.fft.fr,
   - open the developer tools (F12) > Application (Chrome) or Storage (Firefox) > Cookies > `https://tenup.fft.fr`,
   - copy the cookie whose name starts with `SESS` and paste it as `SESSxxxx=value`.

When the session expires, Home Assistant raises a repair asking for a fresh cookie. No password is ever stored.

Options: number of days to fetch (default 7, the club horizon) and refresh interval (default 15 minutes).

## Services

```yaml
service: tenup.book
data:
  court_id: "21100"          # see the attributes of the sensors or the planning command
  start: "2026-09-10 21:00:00"
```

```yaml
service: tenup.cancel
data:
  reservation_id: "165841846"   # or court_id + start
```

Both services return a response (`response_variable`) and raise a readable error when Ten'Up refuses (for example the club rule on simultaneous reservations).

Only slots that require a single player are bookable for now. Courts that require two players (partner) are reported with an explicit error.

## Notes

- Ten'Up cancels a reservation without asking for confirmation. The service does exactly that, so wire a confirmation in your automations or dashboards.
- The public search API is used to find the club, everything else goes through your session.

## Support

Issues and ideas: [GitHub issues](https://github.com/ADNPolymerase/ha-tenup-resa/issues).
