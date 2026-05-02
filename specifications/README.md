# Treehouse Dashboard

Specification and implementation notes for the Treehouse dashboard.

## Overview

The Treehouse dashboard is a local, single-page home telemetry dashboard with two frontends:

- `index.html` — desktop / large-screen dashboard
- `loki.html` — mobile-optimized dashboard

Both pages read the same generated snapshot:

- `dashboard-snapshot.json`

The snapshot is built by:

- `scripts/refresh_dashboard_snapshot.py`

That script aggregates data from:

- Enphase solar
- Sigen battery / grid Modbus snapshot
- Ecowitt weather station
- BOM daily forecast
- Sensibo AC units
- Philips Hue lights
- Hydrawise irrigation schedule/status

## Main files

- `dashboard/index.html` — desktop UI
- `dashboard/loki.html` — mobile UI
- `dashboard/server.py` — static file server only
- `dashboard/update_service.py` — static file server + update API + scheduler
- `dashboard/dashboard-snapshot.json` — main combined dashboard payload
- `dashboard/data.json` — raw power snapshot only
- `dashboard/update_state.json` — persisted scheduler/update state
- `scripts/refresh_dashboard_snapshot.py` — snapshot builder
- `scripts/energy_snapshot.py` — power snapshot builder

---

## Runtime model

### 1. Snapshot generation

`scripts/refresh_dashboard_snapshot.py`:

1. runs `scripts/energy_snapshot.py --json`
2. fetches current Ecowitt weather data
3. fetches Sensibo room/AC data
4. fetches Hue light state
5. fetches Hydrawise relay data
6. fetches 3-day BOM forecast
7. writes:
   - `dashboard/data.json`
   - `dashboard/dashboard-snapshot.json`

### 2. Serving

There are two ways to serve the dashboard:

#### Option A: static only

`dashboard/server.py`

- serves files from `dashboard/`
- no API
- no scheduled refresh

#### Option B: full update service

`dashboard/update_service.py`

- serves files from `dashboard/`
- exposes update endpoints under `/api/*`
- can periodically regenerate `dashboard-snapshot.json`

---

## Backend API

Base path when using `update_service.py`:

- `http://<host>:8420/`

Default host/port:

- host: `0.0.0.0`
- port: `8420`

### GET `/api/update-status`

Returns scheduler/update state.

#### Response schema

| Field | Type | Nullable | Notes |
|---|---|---:|---|
| `enabled` | boolean | no | Whether automatic updates are enabled |
| `interval_seconds` | integer | no | Update interval, currently `300` |
| `last_update` | string | yes | ISO local timestamp of last successful update |
| `next_update` | number | yes | Unix timestamp seconds for next scheduled update |
| `last_status` | string | yes | Typical values: `idle`, `arming`, `ok`, `paused`, `error` |
| `last_error` | string | yes | Error text from last failed update |
| `now` | number | no | Current Unix timestamp seconds, added at response time |

#### Example

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

### GET `/api/update-on`

Enables automatic updates and schedules an immediate refresh.

#### Response

```json
{
  "ok": true,
  "enabled": true
}
```

### GET `/api/update-off`

Disables automatic updates.

#### Response

```json
{
  "ok": true,
  "enabled": false
}
```

### GET `/api/update-now`

Runs `scripts/refresh_dashboard_snapshot.py` immediately.

#### Response schema

| Field | Type | Nullable | Notes |
|---|---|---:|---|
| `ok` | boolean | no | `true` if snapshot generation succeeded |

#### Success example

```json
{ "ok": true }
```

#### Failure behavior

- HTTP status `500`
- body still returns JSON with `ok: false`

---

## Static data files

### `dashboard-snapshot.json`

This is the main frontend payload consumed by both dashboard UIs.

## `dashboard-snapshot.json` schema

### Root object

| Field | Type | Nullable | Notes |
|---|---|---:|---|
| `captured_at` | string | no | ISO local timestamp from `energy_snapshot.py` |
| `power` | object | no | Full energy snapshot |
| `weather` | object | no | Current weather and soil data |
| `forecast` | array<object> | no | Up to 3 BOM daily forecast entries |
| `ac` | array<object> | no | Sensibo room/AC state |
| `lights` | array<object> | no | Selected Hue lights |
| `garden` | array<object> | no | Hydrawise relay/schedule rows |

---

## `power` object

Produced by `scripts/energy_snapshot.py`.

| Field | Type | Nullable | Notes |
|---|---|---:|---|
| `captured_at` | string | no | ISO local timestamp |
| `battery_config` | object | no | Battery capacity/reserve config |
| `power_config` | object | no | Derived power calculation config |
| `enphase` | object | no | Solar production summary |
| `sigen` | object | no | Battery and grid state |
| `derived` | object | no | Calculated values |

### `power.battery_config`

| Field | Type | Nullable | Notes |
|---|---|---:|---|
| `total_capacity_kwh` | number | no | Total battery capacity |
| `reserve_pct` | number | no | Reserved battery percentage |
| `reserve_kwh` | number | no | Reserved battery energy in kWh |

### `power.power_config`

| Field | Type | Nullable | Notes |
|---|---|---:|---|
| `deadband_kw` | number | no | Deadband applied to battery/grid readings |

### `power.enphase`

| Field | Type | Nullable | Notes |
|---|---|---:|---|
| `system_id` | string | no | Enphase system id |
| `current_power_kw` | number | yes | Current solar generation |
| `energy_today_kwh` | number | yes | Solar energy generated today |
| `energy_lifetime_kwh` | number | yes | Lifetime solar generation |
| `status` | string | yes | Enphase status |
| `source` | string | yes | Enphase source label |
| `last_report_at` | integer | yes | Epoch seconds from Enphase |

### `power.sigen`

| Field | Type | Nullable | Notes |
|---|---|---:|---|
| `battery_soc_pct` | number | yes | Battery state of charge (%) |
| `battery_power_kw` | number | yes | Positive = charging, negative = discharging |
| `battery_mode` | string | no | `charging`, `discharging`, `idle`, `unknown` |
| `battery_remaining_kwh` | number | yes | Total stored energy remaining |
| `battery_usable_remaining_kwh` | number | yes | Remaining energy above reserve |
| `time_to_reserve_hours` | number | yes | Hours until reserve at current discharge |
| `time_to_reserve_human` | string | no | Human-readable duration or `—` |
| `time_to_full_hours` | number | yes | Hours to full at current charge rate |
| `time_to_full_human` | string | no | Human-readable duration or `—` |
| `grid_power_kw` | number | yes | Positive = import, negative = export |
| `grid_mode` | string | no | `import`, `export`, `neutral`, `unknown` |

### `power.derived`

| Field | Type | Nullable | Notes |
|---|---|---:|---|
| `home_load_kw` | number | yes | Derived house load |
| `blackout_runtime_hours` | number | yes | Estimated runtime above reserve at current load |
| `blackout_runtime_human` | string | no | Human-readable duration or `—` |

### Home load calculation

The derived load is calculated as:

```text
home_load_kw = solar_kw + battery_discharge_kw + grid_import_kw
               - battery_charge_kw - grid_export_kw
```

---

## `weather` object

Current data from Ecowitt.

| Field | Type | Nullable | Notes |
|---|---|---:|---|
| `outdoor_temp_c` | number | yes | Outdoor temperature in °C |
| `outdoor_humidity_pct` | number | yes | Outdoor relative humidity (%) |
| `indoor_temp_c` | number | yes | Indoor console temperature in °C |
| `indoor_humidity_pct` | number | yes | Indoor console humidity (%) |
| `wind_kmh` | number | yes | Wind speed in km/h |
| `gust_kmh` | number | yes | Wind gust in km/h |
| `rain_day_mm` | number | yes | Rainfall today in mm |
| `solar_wm2` | number | yes | Solar radiation W/m² |
| `uvi` | number | yes | UV index |
| `pressure_hpa` | number | yes | Relative pressure in hPa |
| `soil_1_pct` | number | yes | Soil moisture channel 1 (%) |
| `soil_2_pct` | number | yes | Soil moisture channel 2 (%) |

Notes:

- Ecowitt API values arrive in imperial units for some fields and are converted in the script.
- `rain_day_mm` may be sourced from `rainfall_piezo.daily` or fallback `rainfall.daily`.

---

## `forecast` array

Source: BOM daily forecast API.

Current endpoint:

- `https://api.weather.bom.gov.au/v1/locations/r651hjf/forecasts/daily`

Each array item is a forecast day.

| Field | Type | Nullable | Notes |
|---|---|---:|---|
| `date` | string | yes | BOM ISO datetime string |
| `label` | string | yes | UI label: `Today`, `Tomorrow`, or weekday |
| `condition` | string | yes | Short forecast summary |
| `detail` | string | yes | Extended forecast text |
| `temp_max_c` | number | yes | Forecast max temp in °C |
| `temp_min_c` | number | yes | Forecast min temp in °C |
| `rain_chance_pct` | number | yes | Rain chance (%) |
| `rain_min_mm` | number | yes | Minimum forecast rain amount |
| `rain_max_mm` | number | yes | Maximum forecast rain amount |
| `uv_max` | number | yes | Max UV index |
| `uv_category` | string | yes | BOM UV category |
| `fire_danger` | string | yes | BOM fire danger text |

Notes:

- Only the first 3 days are currently stored.
- `label` is derived locally in `refresh_dashboard_snapshot.py`.

---

## `ac` array

Source: Sensibo API.

Each item represents one room/pod.

| Field | Type | Nullable | Notes |
|---|---|---:|---|
| `name` | string | yes | Room name |
| `on` | boolean | yes | AC power state |
| `mode` | string | yes | HVAC mode |
| `target_c` | number | yes | Target temperature °C |
| `temp_c` | number | yes | Measured room temperature °C |
| `humidity_pct` | number | yes | Measured room humidity (%) |
| `co2` | number | yes | CO₂ reading |
| `iaq` | number | yes | Indoor air quality index |
| `tvoc` | number | yes | Total volatile organic compounds |

---

## `lights` array

Source: Philips Hue local bridge.

Only selected light ids are included:

- `12`, `13`, `14`, `19`, `21`, `26`, `27`, `28`

Each item:

| Field | Type | Nullable | Notes |
|---|---|---:|---|
| `id` | string | no | Hue light id |
| `name` | string | yes | Light name |
| `on` | boolean | yes | On/off state |
| `bri` | integer | yes | Brightness if present |
| `reachable` | boolean | yes | Hue reachability flag |

---

## `garden` array

Source: Hydrawise `statusschedule.php` response.

Each item:

| Field | Type | Nullable | Notes |
|---|---|---:|---|
| `name` | string | yes | Zone name |
| `status` | string | yes | Relay status from Hydrawise |
| `time` | string | yes | Time/status string from Hydrawise |

---

## `data.json`

`dashboard/data.json` is the raw power-only payload written from `energy_snapshot.py` output.

It has the same schema as the `power` object inside `dashboard-snapshot.json`, except it is stored as the root object.

---

## `update_state.json`

Internal persisted scheduler state written by `update_service.py`.

Schema matches the state fields from `/api/update-status`, except `now` is not persisted.

| Field | Type | Nullable |
|---|---|---:|
| `enabled` | boolean | no |
| `interval_seconds` | integer | no |
| `last_update` | string | yes |
| `next_update` | number | yes |
| `last_status` | string | yes |
| `last_error` | string | yes |

---

## Data sources and mapping summary

| Dashboard section | Source |
|---|---|
| Current weather / soil | Ecowitt |
| 3-day forecast | BOM |
| Solar production | Enphase |
| Battery / grid / derived load | Sigen Modbus + local calculations |
| Interior rooms / AC | Sensibo |
| Lighting | Philips Hue |
| Garden / irrigation | Hydrawise |

---

## Environment/config dependencies

Current implementation expects secrets and config to be available via:

- `secrets/ecowitt.env`

Used variables include:

- `ECOWITT_APPLICATION_KEY`
- `ECOWITT_API_KEY`
- `ECOWITT_MAC`
- `SENSIBO_API_KEY`
- `HUE_BRIDGE_IP`
- `HUE_USERNAME`
- `HYDRAWISE_API_KEY`
- `ENPHASE_SYSTEM_ID` (optional override in `energy_snapshot.py`)
- `SIGEN_BATTERY_TOTAL_KWH` (optional override)
- `SIGEN_BATTERY_RESERVE_PCT` (optional override)
- `ENERGY_POWER_DEADBAND_KW` (optional override)
- `DASHBOARD_HOST` (optional)
- `DASHBOARD_PORT` (optional)

---

## Running

### Static server only

```bash
cd /Users/tawnyclaw/.openclaw/workspace/dashboard
python3 server.py
```

### Full update service

```bash
cd /Users/tawnyclaw/.openclaw/workspace/dashboard
python3 update_service.py
```

### Manual snapshot refresh

```bash
cd /Users/tawnyclaw/.openclaw/workspace
python3 scripts/refresh_dashboard_snapshot.py
```

---

## Notes / quirks

- State-changing API endpoints currently use `GET`, not `POST`.
- `server.py` does not provide the `/api/*` endpoints.
- `update_service.py` refresh interval is hardcoded to 300 seconds.
- BOM forecast is used for outlook; Ecowitt is used for live local conditions.
- The dashboard is designed around local/private use, not a public hardened API.

---

## Suggested future improvements

- Move update endpoints to `POST`
- Add explicit JSON schema files
- Add CORS / auth if ever exposed beyond LAN
- Add station metadata for BOM observations if live BOM obs are later included
- Add version field to `dashboard-snapshot.json`
- Add health endpoint for datasource freshness
