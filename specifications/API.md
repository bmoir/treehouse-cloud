# Treehouse Dashboard API

API reference for the Treehouse dashboard backend.

## Overview

The dashboard backend is provided by:

- `dashboard/update_service.py`

It serves:

- static dashboard files
- update/scheduler control endpoints

If you use `dashboard/server.py` instead, the API endpoints below do **not** exist.

Default base URL:

- `http://0.0.0.0:8420`

In practice, replace with your host/IP.

---

## Static routes

### `GET /`

Serves the desktop dashboard:

- `index.html`

### `GET /index.html`

Serves the desktop dashboard.

### `GET /loki.html`

Serves the mobile dashboard.

### `GET /dashboard-snapshot.json`

Returns the latest generated combined snapshot used by both frontends.

### `GET /data.json`

Returns the latest power-only snapshot.

### `GET /update_state.json`

Returns the persisted scheduler state file.

---

## Control API

## `GET /api/update-status`

Returns current scheduler state.

### Response fields

| Field | Type | Nullable | Description |
|---|---|---:|---|
| `enabled` | boolean | no | Whether scheduled updates are enabled |
| `interval_seconds` | integer | no | Update interval in seconds |
| `last_update` | string | yes | ISO timestamp of last successful update |
| `next_update` | number | yes | Unix timestamp for next scheduled update |
| `last_status` | string | yes | `idle`, `arming`, `ok`, `paused`, or `error` |
| `last_error` | string | yes | Error text from the last failed run |
| `now` | number | no | Current Unix timestamp at response time |

### Example

```json
{
  "enabled": true,
  "interval_seconds": 300,
  "last_update": "2026-04-25T11:04:56",
  "next_update": 1777080596.123,
  "last_status": "ok",
  "last_error": null,
  "now": 1777080310.456
}
```

---

## `GET /api/update-on`

Enables automatic scheduled updates.

Behavior:

- sets `enabled = true`
- sets `next_update = time.time()`
- sets `last_status = "arming"`

### Response

```json
{
  "ok": true,
  "enabled": true
}
```

---

## `GET /api/update-off`

Disables automatic scheduled updates.

Behavior:

- sets `enabled = false`
- clears `next_update`
- sets `last_status = "paused"`

### Response

```json
{
  "ok": true,
  "enabled": false
}
```

---

## `GET /api/update-now`

Triggers an immediate snapshot refresh by executing:

- `scripts/refresh_dashboard_snapshot.py`

If scheduled updates are enabled, this also pushes `next_update` forward by `interval_seconds`.

### Success response

Status:

- `200 OK`

Body:

```json
{
  "ok": true
}
```

### Failure response

Status:

- `500 Internal Server Error`

Body:

```json
{
  "ok": false
}
```

---

## Snapshot payloads

## `GET /dashboard-snapshot.json`

Primary combined payload for the dashboards.

### Top-level fields

| Field | Type |
|---|---|
| `captured_at` | string |
| `power` | object |
| `weather` | object |
| `forecast` | array |
| `ac` | array |
| `lights` | array |
| `garden` | array |

For full field-by-field schema, see:

- `README.md`
- `schema.json`

---

## `GET /data.json`

Power-only snapshot written from `scripts/energy_snapshot.py`.

### Top-level fields

| Field | Type |
|---|---|
| `captured_at` | string |
| `battery_config` | object |
| `power_config` | object |
| `enphase` | object |
| `sigen` | object |
| `derived` | object |

---

## Internal state file

## `GET /update_state.json`

This is the persisted scheduler state file written by `update_service.py`.

Typical fields:

| Field | Type | Nullable |
|---|---|---:|
| `enabled` | boolean | no |
| `interval_seconds` | integer | no |
| `last_update` | string | yes |
| `next_update` | number | yes |
| `last_status` | string | yes |
| `last_error` | string | yes |

---

## Notes

- State-changing endpoints currently use `GET`, not `POST`.
- There is no auth layer in the current implementation.
- This backend is intended for local/private use.
- Scheduled refresh interval is currently hardcoded to `300` seconds.
- Static file serving and API are handled by the same Python process in `update_service.py`.
