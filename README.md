# Treehouse Cloud Dashboard

Home telemetry dashboard running on AWS (Lambda + DynamoDB + API Gateway + CloudFront + S3).  
Data is pushed from the home every 10 minutes. The dashboard auto-refreshes on the same interval.

Live URL: `https://d343mj1ly4j9wa.cloudfront.net/`

---

## Dashboard layout

Three-column full-viewport layout, tuned for 2560 × 1664.

```
┌────────────────────┬──────────────────────────┬────────────────────┐
│  Sky / Weather     │                          │  Battery Reserve   │
│  Envelope          │   Exterior Future        │  Logic             │
├────────────────────│   (house diagram +        ├────────────────────┤
│  Solar & Grid      │    3-day forecast)        │  Lighting          │
│  Exchange          │                          │  Constellation     │
├────────────────────│                          ├────────────────────┤
│  Garden / Soil /   ├──────────────────────────│  Interior          │
│  Watering          │  Water Tank Reserve      │  Atmosphere        │
└────────────────────┴──────────────────────────┴────────────────────┘
```

### Column 1 — Left (sky → ground)

| Panel | Contents |
|---|---|
| **Sky / Weather Envelope** | Outdoor temp, wind, humidity, rain, solar irradiance, barometric pressure |
| **Solar & Grid Exchange** | Solar generation, home load, grid import/export — each as a value + bar |
| **Garden / Soil / Watering** | Soil moisture (2 channels), solar radiance, UV index, irrigation zone schedule |

### Column 2 — Centre (house + future)

| Panel | Contents |
|---|---|
| **Exterior Future** | House floor-plan diagram with per-room temperature, humidity, AC state, CO₂/IAQ/TVOC. Solar generation summary tile. 3-day BOM weather forecast ribbon at the bottom. |
| **Water Tank Reserve** | Animated cross-section SVG of the concrete tank: depth-to-water scale (left), percent + 110 kL capacity label (right), current volume in litres overlaid on water, wave animation, sensor beam. |

### Column 3 — Right (energy + comfort)

| Panel | Contents |
|---|---|
| **Battery Reserve Logic** | SOC %, remaining kWh, usable kWh, reserve kWh, time-to-reserve, blackout runtime estimate |
| **Lighting Constellation** | On/off state for 8 selected Philips Hue lights |
| **Interior Atmosphere** | Per-room card: large temp + humidity, AC status. Lounge room also shows CO₂, IAQ, TVOC. |

---

## Data snapshot — fields and sample values

The main snapshot is fetched from `GET /snapshot`. All fields can be null unless noted.

### Root

```json
{
  "captured_at": "2026-05-02T08:34:12",
  "power":   { ... },
  "weather": { ... },
  "forecast": [ ... ],
  "ac":       [ ... ],
  "lights":   [ ... ],
  "garden":   [ ... ]
}
```

---

### `power` object

Source: Enphase solar API + Sigen battery/grid Modbus.

#### `power.battery_config`

| Field | Sample | Notes |
|---|---|---|
| `total_capacity_kwh` | `15.0` | Total battery bank capacity |
| `reserve_pct` | `20.0` | Reserved percentage (not used for load) |
| `reserve_kwh` | `3.0` | Equivalent reserved energy |

#### `power.enphase` — solar production

| Field | Sample | Notes |
|---|---|---|
| `system_id` | `"12345678"` | Enphase system identifier |
| `current_power_kw` | `4.2` | Current solar output |
| `energy_today_kwh` | `18.4` | Solar generated today |
| `energy_lifetime_kwh` | `12540.0` | All-time generation |
| `status` | `"normal"` | Enphase system status |
| `last_report_at` | `1746160800` | Unix epoch of last panel report |

#### `power.sigen` — battery and grid

| Field | Sample | Notes |
|---|---|---|
| `battery_soc_pct` | `78.0` | State of charge % |
| `battery_power_kw` | `1.2` | Positive = charging, negative = discharging |
| `battery_mode` | `"charging"` | `charging` / `discharging` / `idle` / `unknown` |
| `battery_remaining_kwh` | `11.7` | Total energy currently stored |
| `battery_usable_remaining_kwh` | `8.7` | Stored energy above the reserve floor |
| `time_to_reserve_hours` | `null` | Hours until reserve hit (null if charging) |
| `time_to_reserve_human` | `"—"` | Human-readable, e.g. `"4h 20m"` |
| `time_to_full_hours` | `3.2` | Hours to full charge (null if discharging) |
| `time_to_full_human` | `"3h 12m"` | Human-readable |
| `grid_power_kw` | `-0.8` | Positive = import, negative = export |
| `grid_mode` | `"export"` | `import` / `export` / `neutral` / `unknown` |

#### `power.derived` — calculated values

| Field | Sample | Notes |
|---|---|---|
| `home_load_kw` | `2.6` | Current whole-home consumption |
| `blackout_runtime_hours` | `3.4` | Estimated battery runtime above reserve at current load |
| `blackout_runtime_human` | `"3h 24m"` | Human-readable |

---

### `weather` object

Source: Ecowitt weather station (outdoor + console sensors).

| Field | Sample | Notes |
|---|---|---|
| `outdoor_temp_c` | `24.6` | Outside air temperature |
| `outdoor_humidity_pct` | `58.0` | Outside relative humidity |
| `indoor_temp_c` | `22.1` | Ecowitt console indoor temperature |
| `indoor_humidity_pct` | `52.0` | Ecowitt console indoor humidity |
| `wind_kmh` | `14.0` | Wind speed |
| `gust_kmh` | `22.0` | Wind gust |
| `rain_day_mm` | `3.2` | Rainfall total for today |
| `solar_wm2` | `820.0` | Solar irradiance W/m² |
| `uvi` | `6.2` | UV index |
| `pressure_hpa` | `1016.4` | Relative barometric pressure |
| `soil_1_pct` | `34.0` | Soil moisture sensor channel 1 |
| `soil_2_pct` | `41.0` | Soil moisture sensor channel 2 |

---

### `forecast` array

Source: BOM daily forecast API. Up to 3 days returned.

```json
[
  {
    "date": "2026-05-02T00:00:00Z",
    "label": "Today",
    "condition": "Partly cloudy",
    "detail": "Areas of cloud. Medium chance of showers.",
    "temp_max_c": 27.0,
    "temp_min_c": 14.0,
    "rain_chance_pct": 40.0,
    "rain_min_mm": 1.0,
    "rain_max_mm": 8.0,
    "uv_max": 6.0,
    "uv_category": "High",
    "fire_danger": null
  },
  {
    "date": "2026-05-03T00:00:00Z",
    "label": "Tomorrow",
    "condition": "Sunny",
    "detail": "Mostly sunny.",
    "temp_max_c": 29.0,
    "temp_min_c": 15.0,
    "rain_chance_pct": 5.0,
    "rain_min_mm": 0.0,
    "rain_max_mm": 0.0,
    "uv_max": 8.0,
    "uv_category": "Very High",
    "fire_danger": "Low-Moderate"
  },
  {
    "date": "2026-05-04T00:00:00Z",
    "label": "Sunday",
    "condition": "Shower or two",
    "detail": "Cloud increasing. Rain developing.",
    "temp_max_c": 22.0,
    "temp_min_c": 13.0,
    "rain_chance_pct": 70.0,
    "rain_min_mm": 4.0,
    "rain_max_mm": 15.0,
    "uv_max": 3.0,
    "uv_category": "Moderate",
    "fire_danger": null
  }
]
```

---

### `ac` array

Source: Sensibo API. Two rooms: **Bedroom** and **Lounge Room**.  
Air quality sensors (`co2`, `iaq`, `tvoc`) are only fitted in the Lounge — they are `null` for Bedroom.

```json
[
  {
    "name": "Bedroom",
    "on": false,
    "mode": "cool",
    "target_c": 22.0,
    "temp_c": 21.8,
    "humidity_pct": 64.0,
    "co2": null,
    "iaq": null,
    "tvoc": null
  },
  {
    "name": "Lounge Room",
    "on": true,
    "mode": "cool",
    "target_c": 24.0,
    "temp_c": 23.4,
    "humidity_pct": 58.0,
    "co2": 812.0,
    "iaq": 84.0,
    "tvoc": 1.2
  }
]
```

| Field | Notes |
|---|---|
| `name` | Room name — `"Bedroom"` or `"Lounge Room"` |
| `on` | AC unit power state |
| `mode` | HVAC mode: `cool`, `heat`, `fan`, `auto`, `dry` |
| `target_c` | Set-point temperature |
| `temp_c` | Measured room temperature |
| `humidity_pct` | Measured room humidity |
| `co2` | CO₂ in ppm — Lounge only |
| `iaq` | Indoor Air Quality index (0–500, lower is better) — Lounge only |
| `tvoc` | Total Volatile Organic Compounds — Lounge only |

---

### `lights` array

Source: Philips Hue local bridge. 8 selected lights included.

```json
[
  { "id": "12", "name": "Entry",         "on": true,  "bri": 180, "reachable": true  },
  { "id": "13", "name": "Kitchen",       "on": true,  "bri": 220, "reachable": true  },
  { "id": "14", "name": "Lounge",        "on": false, "bri": 0,   "reachable": true  },
  { "id": "19", "name": "Dining",        "on": true,  "bri": 150, "reachable": true  },
  { "id": "21", "name": "Master",        "on": false, "bri": 0,   "reachable": true  },
  { "id": "26", "name": "Bedroom 2",     "on": false, "bri": 0,   "reachable": true  },
  { "id": "27", "name": "Outdoor Front", "on": true,  "bri": 254, "reachable": true  },
  { "id": "28", "name": "Outdoor Rear",  "on": false, "bri": 0,   "reachable": false }
]
```

| Field | Notes |
|---|---|
| `id` | Hue bridge light ID |
| `name` | Light/zone name |
| `on` | On/off state |
| `bri` | Brightness 0–254 |
| `reachable` | Whether Hue bridge can reach the bulb |

---

### `garden` array

Source: Hydrawise irrigation controller. Up to 8 zones.

```json
[
  { "name": "Front Lawn",    "status": "idle",    "time": "Next: Tomorrow 06:00" },
  { "name": "Rear Garden",   "status": "idle",    "time": "Next: Sat 06:00"      },
  { "name": "Veg Patch",     "status": "running", "time": "Stops in 8 min"       },
  { "name": "Side Path",     "status": "idle",    "time": "Next: Mon 06:00"      }
]
```

| Field | Notes |
|---|---|
| `name` | Zone/relay name |
| `status` | `"idle"` or `"running"` |
| `time` | Human-readable next-run or remaining time string |

---

## Water tank data — separate endpoint

The water tank uses its own DynamoDB records and API routes, independent of the main snapshot.

### `GET /tank/snapshot` — latest reading

```json
{
  "distance_cm": 77.7,
  "percent": 68.9,
  "litres": 76133,
  "captured_at": "2026-05-02T08:34:07"
}
```

| Field | Notes |
|---|---|
| `distance_cm` | Ultrasonic sensor distance from sensor to water surface (1 dp). Sensor is mounted at the top of the tank. |
| `percent` | How full the tank is, 0–100 (1 dp) |
| `litres` | Volume of water, whole number |
| `captured_at` | UTC timestamp of the reading |

**Tank physical spec:** Round concrete tank, 2.5 m deep, 110,446 L at 100% full.  
**Colour coding on dashboard:** teal ≥ 60% · muted teal 25–59% · orange < 25%

### `POST /tank` — ingest endpoint (device → API)

```
POST /tank
Content-Type: application/json
X-API-Key: <key>

{ "distance_cm": 77.7, "percent": 68.9, "litres": 76133 }
```

History stored for 90 days with TTL, queryable by time range from DynamoDB (`pk: "tank"`, `sk: ISO timestamp`).

---

## API endpoints

Base URL: `https://d343mj1ly4j9wa.cloudfront.net`

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/ingest` | `X-API-Key` | Push full home snapshot (main dashboard data) |
| `GET` | `/snapshot` | None | Latest home snapshot |
| `GET` | `/history?hours=N` | None | Snapshot history, 1–168 h window (default 24 h) |
| `POST` | `/tank` | `X-API-Key` | Push water tank sensor reading |
| `GET` | `/tank/snapshot` | None | Latest tank reading |

---

## Infrastructure

| Component | Service | Notes |
|---|---|---|
| API & data ingestion | AWS Lambda (Python 3.12) | Single function handles all routes |
| Database | DynamoDB (on-demand) | `pk/sk` keyed; TTL-expiry on history records after 90 days |
| API gateway | API Gateway HTTP API v2 | Routes: `/ingest`, `/snapshot`, `/history`, `/tank`, `/tank/snapshot` |
| CDN + routing | CloudFront | S3 for static HTML; API Gateway as second origin for `/snapshot`, `/history`, `/ingest`, `/tank*` |
| Frontend hosting | S3 (private, OAC) | `index.html` (desktop), `loki.html` (mobile) |
| Secrets | SSM Parameter Store | API key at `/treehouse/api-key` (SecureString) |
| IaC | CloudFormation | `infra/cloudformation.yaml` — single-region stack |

**Deploy commands:**

```bash
# Full deploy (CloudFormation + frontend)
AWS_PROFILE=treehouse make deploy

# Frontend HTML only (fast, no CloudFormation)
AWS_PROFILE=treehouse make deploy-frontend

# Lambda code only (after editing api/handler.py)
AWS_PROFILE=treehouse make deploy-api

# Rotate API key
AWS_PROFILE=treehouse make create-key

# Print stack outputs (URLs, bucket name)
AWS_PROFILE=treehouse make outputs
```

> **Note:** `make deploy` updates CloudFormation infrastructure but does **not** re-push Lambda code unless the template changes. Always run `make deploy-api` after editing `api/handler.py`.

---

## Data push cadence

- **Home snapshot** (`/ingest`): every 10 minutes from the home server
- **Water tank** (`/tank`): pushed by the ultrasonic sensor device on its own schedule
- **Dashboard auto-refresh**: every 10 minutes; shows a stale warning if data is > 25 minutes old
