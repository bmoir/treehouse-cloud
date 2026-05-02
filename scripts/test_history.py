#!/usr/bin/env python3
"""
Integration test: pushes a snapshot to /ingest then verifies it appears
in both the /history API endpoint and directly in DynamoDB.

Run from the project root:
    python3 scripts/test_history.py

Env overrides:
    STACK_NAME   (default: treehouse-cloud)
    REGION       (default: ap-southeast-2)
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone

import boto3

STACK_NAME = os.environ.get('STACK_NAME', 'treehouse-cloud')
REGION     = os.environ.get('REGION', 'ap-southeast-2')

PASS = '[PASS]'
FAIL = '[FAIL]'

# ── Minimal valid snapshot matching dashboard-snapshot.json schema ─────────

def make_test_snapshot(tag: str) -> dict:
    return {
        "captured_at": tag,
        "power": {
            "captured_at": tag,
            "battery_config": {
                "total_capacity_kwh": 20.0,
                "reserve_pct": 10.0,
                "reserve_kwh": 2.0
            },
            "power_config": {"deadband_kw": 0.05},
            "enphase": {
                "system_id": "test-system",
                "current_power_kw": 3.5,
                "energy_today_kwh": 12.0,
                "energy_lifetime_kwh": 5000.0,
                "status": "normal",
                "source": "enlighten",
                "last_report_at": 1700000000
            },
            "sigen": {
                "battery_soc_pct": 85.0,
                "battery_power_kw": 1.2,
                "battery_mode": "charging",
                "battery_remaining_kwh": 14.0,
                "battery_usable_remaining_kwh": 12.0,
                "time_to_reserve_hours": None,
                "time_to_reserve_human": "-",
                "time_to_full_hours": 1.5,
                "time_to_full_human": "1h 30m",
                "grid_power_kw": 0.0,
                "grid_mode": "neutral"
            },
            "derived": {
                "home_load_kw": 2.3,
                "blackout_runtime_hours": 5.2,
                "blackout_runtime_human": "5h 12m"
            }
        },
        "weather": {
            "outdoor_temp_c": 22.5,
            "outdoor_humidity_pct": 65.0,
            "indoor_temp_c": 21.0,
            "indoor_humidity_pct": 60.0,
            "wind_kmh": 12.0,
            "gust_kmh": 18.0,
            "rain_day_mm": 0.0,
            "solar_wm2": 650.0,
            "uvi": 5.0,
            "pressure_hpa": 1013.0,
            "soil_1_pct": 45.0,
            "soil_2_pct": 50.0
        },
        "forecast": [],
        "ac": [],
        "lights": [],
        "garden": []
    }


# ── Helpers ────────────────────────────────────────────────────────────────

def get_stack_output(cfn_client, key: str) -> str:
    resp = cfn_client.describe_stacks(StackName=STACK_NAME)
    for o in resp['Stacks'][0]['Outputs']:
        if o['OutputKey'] == key:
            return o['OutputValue']
    raise ValueError(f"Output key '{key}' not found in stack '{STACK_NAME}'")


def get_api_key(ssm_client) -> str:
    resp = ssm_client.get_parameter(Name='/treehouse/api-key', WithDecryption=True)
    return resp['Parameter']['Value']


def http_post(url: str, payload: dict, api_key: str) -> tuple[int, dict]:
    body = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            'Content-Type': 'application/json',
            'X-API-Key': api_key,
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def http_get(url: str) -> tuple[int, object]:
    req = urllib.request.Request(url, method='GET')
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def section(title: str):
    print(f"\n{title}")
    print('-' * len(title))


def check(label: str, condition: bool, detail: str = ''):
    tag = PASS if condition else FAIL
    line = f"  {tag}  {label}"
    if detail:
        line += f"  ({detail})"
    print(line)
    if not condition:
        sys.exit(1)


# ── Test ───────────────────────────────────────────────────────────────────

def main():
    print(f"Treehouse history integration test")
    print(f"Stack: {STACK_NAME}  Region: {REGION}")

    # ── 1. Resolve config from AWS ─────────────────────────────────────────
    section("1. Resolving config from AWS")

    cfn = boto3.client('cloudformation', region_name=REGION)
    ssm = boto3.client('ssm', region_name=REGION)
    ddb = boto3.resource('dynamodb', region_name=REGION)

    try:
        cf_domain = get_stack_output(cfn, 'CloudFrontDomain')
        check("CloudFront domain found", bool(cf_domain), cf_domain)
    except Exception as e:
        check("CloudFront domain found", False, str(e))

    try:
        table_name = get_stack_output(cfn, 'LambdaFunctionName')
        # Derive table name from function name (same prefix)
        table_name = cf_domain.split('.')[0]   # not used; we build it below
    except Exception:
        pass

    # Table name follows the CFN convention: <stack-name>-snapshots
    ddb_table_name = f"{STACK_NAME}-snapshots"
    table = ddb.Table(ddb_table_name)

    try:
        api_key = get_api_key(ssm)
        check("API key retrieved from SSM", bool(api_key), f"{len(api_key)} chars")
    except Exception as e:
        check("API key retrieved from SSM", False, str(e))

    ingest_url  = f"https://{cf_domain}/ingest"
    history_url = f"https://{cf_domain}/history?hours=1"

    # ── 2. Push a uniquely tagged test snapshot ────────────────────────────
    section("2. Pushing test snapshot to /ingest")

    tag = f"TEST-{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')}Z"
    snapshot = make_test_snapshot(tag)

    print(f"  captured_at tag: {tag}")
    status, body = http_post(ingest_url, snapshot, api_key)
    check(f"POST /ingest returned 200", status == 200, f"got {status}: {body}")
    check("Response ok=true", body.get('ok') is True, str(body))

    # Short wait for Lambda + DynamoDB write to settle
    time.sleep(2)

    # ── 3. Verify via /history API ─────────────────────────────────────────
    section("3. Verifying via GET /history?hours=1")

    status, items = http_get(history_url)
    check(f"GET /history returned 200", status == 200, f"got {status}")
    check("Response is a list", isinstance(items, list), f"got {type(items).__name__}")
    check("At least one item in history", len(items) > 0, f"got {len(items)} items")

    matched = [i for i in items if i.get('captured_at') == tag]
    check(
        f"Test snapshot found in /history by captured_at",
        len(matched) == 1,
        f"found {len(matched)} matches for tag '{tag}' across {len(items)} items"
    )

    # ── 4. Verify directly in DynamoDB ────────────────────────────────────
    section("4. Verifying directly in DynamoDB")

    from boto3.dynamodb.conditions import Key

    # History records: pk="snapshot", sk=ingested_at UTC timestamp
    cutoff = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
    # Query last 5 minutes worth of records (sk is UTC ISO string, lexicographic sort works)
    from datetime import timedelta
    cutoff_5m = (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime('%Y-%m-%dT%H:%M:%S')

    result = table.query(
        KeyConditionExpression=Key('pk').eq('snapshot') & Key('sk').gte(cutoff_5m),
        ScanIndexForward=False,
        Limit=50,
    )
    raw_items = result.get('Items', [])
    check(
        "DynamoDB history partition has recent records",
        len(raw_items) > 0,
        f"{len(raw_items)} records in last 5 min"
    )

    ddb_matched = [
        i for i in raw_items
        if i.get('payload', {}).get('captured_at') == tag
    ]
    check(
        "Test snapshot found in DynamoDB history partition",
        len(ddb_matched) == 1,
        f"found {len(ddb_matched)} matches across {len(raw_items)} recent records"
    )

    item = ddb_matched[0]
    check("DynamoDB item has ttl set",    'ttl' in item,         f"ttl={item.get('ttl')}")
    check("DynamoDB item has ingested_at", 'ingested_at' in item, f"ingested_at={item.get('ingested_at')}")
    check("DynamoDB pk='snapshot'",       item.get('pk') == 'snapshot')

    # ── 5. Verify /snapshot (latest) also updated ─────────────────────────
    section("5. Verifying GET /snapshot reflects latest push")

    snapshot_url = f"https://{cf_domain}/snapshot"
    status, latest = http_get(snapshot_url)
    check(f"GET /snapshot returned 200", status == 200, f"got {status}")
    check(
        "Latest snapshot captured_at matches test tag",
        latest.get('captured_at') == tag,
        f"got '{latest.get('captured_at')}', expected '{tag}'"
    )

    # ── Done ───────────────────────────────────────────────────────────────
    print(f"\nAll checks passed. History is being saved correctly.")
    print(f"DynamoDB table: {ddb_table_name}")
    print(f"  pk='latest'   sk='latest'    -> always-current snapshot")
    print(f"  pk='snapshot' sk=<utc-time>  -> append-only history (90-day TTL)")


if __name__ == '__main__':
    main()
