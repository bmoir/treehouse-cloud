import json
import os
import time
import hmac
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key as DKey

_dynamodb = boto3.resource('dynamodb')
_ssm = boto3.client('ssm')

TABLE_NAME = os.environ['TABLE_NAME']
API_KEY_PARAM = os.environ['API_KEY_PARAM']

_table = _dynamodb.Table(TABLE_NAME)

HISTORY_TTL_DAYS = 90
MAX_HISTORY_HOURS = 168  # 7-day cap on /history queries

_cached_key = None
_key_fetched_at = 0.0
_KEY_CACHE_TTL = 300  # re-read SSM at most every 5 minutes

_CORS = {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': '*',
}


def _get_api_key() -> str:
    global _cached_key, _key_fetched_at
    now = time.monotonic()
    if _cached_key and now - _key_fetched_at < _KEY_CACHE_TTL:
        return _cached_key
    resp = _ssm.get_parameter(Name=API_KEY_PARAM, WithDecryption=True)
    _cached_key = resp['Parameter']['Value']
    _key_fetched_at = now
    return _cached_key


def _resp(status: int, body) -> dict:
    return {
        'statusCode': status,
        'headers': _CORS,
        'body': json.dumps(body),
    }


def _to_decimal(obj):
    """Recursively convert Python floats to Decimal for DynamoDB storage."""
    if obj is None:
        return None
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_decimal(i) for i in obj]
    return obj


def _from_decimal(obj):
    """Recursively convert Decimal back to float for JSON serialisation."""
    if obj is None:
        return None
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _from_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_from_decimal(i) for i in obj]
    return obj


def handler(event, context):
    ctx = event.get('requestContext', {}).get('http', {})
    method = ctx.get('method', '')
    path = event.get('rawPath', '')

    if method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                **_CORS,
                'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type,X-API-Key',
            },
            'body': '',
        }

    if method == 'POST' and path == '/ingest':
        return _handle_ingest(event)
    if method == 'GET' and path == '/snapshot':
        return _handle_snapshot()
    if method == 'GET' and path == '/history':
        return _handle_history(event)
    if method == 'POST' and path == '/tank':
        return _handle_tank_ingest(event)
    if method == 'GET' and path == '/tank/snapshot':
        return _handle_tank_snapshot()

    return _resp(404, {'error': 'not found'})


def _handle_ingest(event):
    # Validate API key via constant-time comparison
    headers = {k.lower(): v for k, v in (event.get('headers') or {}).items()}
    provided = headers.get('x-api-key', '')

    try:
        expected = _get_api_key()
    except _ssm.exceptions.ParameterNotFound:
        return _resp(503, {'ok': False, 'error': 'service not configured — run create_key.sh'})

    if not hmac.compare_digest(provided, expected):
        return _resp(401, {'ok': False, 'error': 'unauthorized'})

    # Decode body
    body = event.get('body') or ''
    if event.get('isBase64Encoded'):
        import base64
        body = base64.b64decode(body).decode('utf-8')

    try:
        snapshot = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return _resp(400, {'ok': False, 'error': 'invalid json'})

    captured_at = snapshot.get('captured_at', '')
    if not captured_at:
        return _resp(400, {'ok': False, 'error': 'missing captured_at'})

    now_ts = int(time.time())
    ingested_at_utc = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
    ttl = now_ts + HISTORY_TTL_DAYS * 86400

    payload = _to_decimal(snapshot)

    # Always-current record — overwritten each push
    _table.put_item(Item={
        'pk': 'latest',
        'sk': 'latest',
        'payload': payload,
        'captured_at': captured_at,
        'ingested_at': now_ts,
    })

    # Append-only history record — TTL-expired after 90 days
    _table.put_item(Item={
        'pk': 'snapshot',
        'sk': ingested_at_utc,
        'payload': payload,
        'captured_at': captured_at,
        'ingested_at': now_ts,
        'ttl': ttl,
    })

    return _resp(200, {'ok': True})


def _handle_snapshot():
    result = _table.get_item(Key={'pk': 'latest', 'sk': 'latest'})
    item = result.get('Item')
    if not item:
        return _resp(404, {'error': 'no snapshot available yet'})
    return _resp(200, _from_decimal(item['payload']))


def _handle_tank_ingest(event):
    headers = {k.lower(): v for k, v in (event.get('headers') or {}).items()}
    provided = headers.get('x-api-key', '')
    try:
        expected = _get_api_key()
    except _ssm.exceptions.ParameterNotFound:
        return _resp(503, {'ok': False, 'error': 'service not configured — run create_key.sh'})
    if not hmac.compare_digest(provided, expected):
        return _resp(401, {'ok': False, 'error': 'unauthorized'})

    body = event.get('body') or ''
    if event.get('isBase64Encoded'):
        import base64
        body = base64.b64decode(body).decode('utf-8')
    try:
        data = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return _resp(400, {'ok': False, 'error': 'invalid json'})

    for field in ('distance_cm', 'percent', 'litres'):
        if field not in data:
            return _resp(400, {'ok': False, 'error': f'missing {field}'})

    now_ts = int(time.time())
    captured_at = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
    ttl = now_ts + HISTORY_TTL_DAYS * 86400

    payload = _to_decimal({
        'distance_cm': data['distance_cm'],
        'percent': data['percent'],
        'litres': int(data['litres']),
        'captured_at': captured_at,
    })

    _table.put_item(Item={
        'pk': 'tank-latest',
        'sk': 'latest',
        'payload': payload,
        'captured_at': captured_at,
        'ingested_at': now_ts,
    })
    _table.put_item(Item={
        'pk': 'tank',
        'sk': captured_at,
        'payload': payload,
        'captured_at': captured_at,
        'ingested_at': now_ts,
        'ttl': ttl,
    })
    return _resp(200, {'ok': True})


def _handle_tank_snapshot():
    result = _table.get_item(Key={'pk': 'tank-latest', 'sk': 'latest'})
    item = result.get('Item')
    if not item:
        return _resp(404, {'error': 'no tank data yet'})
    return _resp(200, _from_decimal(item['payload']))


def _handle_history(event):
    params = event.get('queryStringParameters') or {}
    try:
        hours = min(MAX_HISTORY_HOURS, max(1, int(params.get('hours', '24'))))
    except (ValueError, TypeError):
        hours = 24

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime('%Y-%m-%dT%H:%M:%S')

    result = _table.query(
        KeyConditionExpression=DKey('pk').eq('snapshot') & DKey('sk').gte(cutoff),
        ScanIndexForward=False,
        Limit=1000,
    )

    items = [_from_decimal(item['payload']) for item in result.get('Items', [])]
    return _resp(200, items)
