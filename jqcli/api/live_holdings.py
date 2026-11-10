"""Read-only intraday quantities from a timestamped baseline and broker fills.

No live valuation is implied. Ambiguous replay boundaries fail closed.
"""
from datetime import datetime
from decimal import Decimal, InvalidOperation
import re
import json
import os
import subprocess
from pathlib import Path
from zoneinfo import ZoneInfo

from jqcli.errors import ApiError, UsageError
from .live import _normalize_position, _require_ok, get_live_positions

ZONE = ZoneInfo('Asia/Shanghai')


def fail(reason):
    raise ApiError(reason, details={'reason': reason})


def number(value):
    try:
        n = Decimal(str(value))
        if not n.is_finite() or n < 0:
            raise ValueError()
        return n
    except (InvalidOperation, ValueError):
        fail('INTRADAY_INVALID_NUMBER')


def shares(value):
    text = re.sub(r'<[^>]*>', '', str(value)).strip()
    if not re.fullmatch(r'\d+(?:股|份)?', text):
        fail('INTRADAY_INVALID_QUANTITY')
    return int(re.sub(r'\D', '', text))


def stamp(value):
    try:
        return datetime.strptime(str(value), '%Y-%m-%d %H:%M:%S')
    except ValueError:
        fail('INTRADAY_INVALID_TIMESTAMP')


def selected_date(value=None):
    value = value or datetime.now(ZONE).date().isoformat()
    try:
        datetime.strptime(value, '%Y-%m-%d')
    except ValueError:
        raise UsageError('日期格式须为 YYYY-MM-DD')
    return value


def read_live_page(live_id, name=None):
    try:
        run = subprocess.run([os.environ.get('JQCLI_NODE', 'node'),
            str(Path(__file__).with_name('live_page.mjs')),
            json.dumps({'id': live_id, 'name': name})], capture_output=True, encoding="utf-8", timeout=45)
        page = json.loads(run.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        fail('PAGE_BROWSER_READ_FAILED')
    if run.returncode or page.get('error'):
        fail(page.get('error', 'PAGE_BROWSER_READ_FAILED'))
    return page


def signed_number(value):
    try:
        n = Decimal(re.sub(r'<[^>]*>', '', str(value)).strip().replace(',', ''))
        if not n.is_finite():
            raise ValueError()
        return n
    except (InvalidOperation, ValueError):
        fail('INTRADAY_INVALID_NUMBER')


def transaction_rows(page, date, limit):
    raw = page['transactions']['rows']
    if page['transactions']['records'] != len(raw) or len(raw) > limit:
        fail('INTRADAY_INCOMPLETE_INPUT')
    if not any(re.search(r'下单详情[（(]' + re.escape(date) + r'[）)]', x) for x in page['dates']):
        fail('PAGE_TRANSACTION_DATE_MISMATCH')
    result = []
    for row in raw:
        match = re.fullmatch(r'(.+)\((\d{6}\.(?:XSHG|XSHE))\)', str(row.get('stock', '')))
        if not match or row.get('security') not in ('股票', '基金'):
            fail('INTRADAY_UNSUPPORTED_ASSET')
        if row.get('date') != date:
            fail('TRANSACTION_DATE_MISMATCH')
        side = row.get('transaction')
        if side not in ('买', '卖'):
            fail('INTRADAY_UNSUPPORTED_TRANSACTION')
        def quantity(value):
            text = re.sub(r'<[^>]*>', '', str(value)).strip().replace(',', '')
            if not re.fullmatch(r'-?\d+(?:股|份)?', text):
                fail('INTRADAY_INVALID_QUANTITY')
            n = int(re.sub(r'[股份]', '', text))
            if n < 0 and side != '卖':
                fail('TRANSACTION_SIGN_MISMATCH')
            return abs(n)
        total = signed_number(row.get('total'))
        if total < 0 and side != '卖':
            fail('TRANSACTION_SIGN_MISMATCH')
        result.append({'code': match[2], 'name': match[1], 'asset_type': row['security'],
            'side': side, 'filled_quantity': quantity(row.get('trueAmount', row.get('amount'))),
            'filled_value': float(abs(total)), 'commission': float(number(row.get('commission'))),
            'status': row.get('status'), 'match_time': row.get('matchTime'),
            'order_quantity': quantity(row.get('trueOrderAmount', row.get('orderAmount'))),
            'order_time': date + ' ' + str(row.get('time', ''))})
    return {'id': page['url'].split('backtestId=')[-1].split('&')[0], 'date': date,
        'source': 'live_page_transaction_table', 'complete': True, 'transactions': result,
        'transaction_count': len(result), 'queried_at': datetime.fromisoformat(page['read_at'].replace('Z', '+00:00')).astimezone(ZONE).isoformat(),
        'page_name': page['name'], 'page_url': page['url']}


def get_live_transactions(client, live_id, *, date=None, limit=1000, name=None, source='api'):
    date = selected_date(date)
    if source == 'page':
        return transaction_rows(read_live_page(live_id, name), date, limit)
    if source != 'api':
        raise UsageError('source must be api or page')
    payload = _require_ok(client.get('/algorithm/live/transactionDetail', params={
        'backtestId': live_id, 'date': date, 'limit': limit,
        'field': '', 'order': '', 'ajax': '1'}))
    data = payload.get('data')
    if (not isinstance(data, dict) or not isinstance(data.get('transaction'), list)
            or data.get('isLimit') is not False or len(data['transaction']) >= limit):
        fail('INTRADAY_INCOMPLETE_INPUT')
    # Reuse the same strict row/sign/date normalizer for both transports.
    page = {'name': name, 'url': 'https://www.joinquant.com/algorithm/live/index?backtestId=' + live_id,
        'read_at': datetime.now(ZONE).isoformat(), 'dates': ['下单详情(' + date + ')'],
        'transactions': {'rows': data['transaction'], 'records': len(data['transaction'])}}
    result = transaction_rows(page, date, limit)
    result.update(source='live_transaction_api', endpoint='/algorithm/live/transactionDetail',
                  completeness={'is_limit': False, 'row_count': len(data['transaction']), 'limit': limit})
    result.pop('page_url', None)
    result.pop('page_name', None)
    return result


def reconstruct(snapshot, transactions):
    date = transactions['date']
    if snapshot.get('is_limit') is not False or not transactions.get('complete'):
        fail('INTRADAY_INCOMPLETE_INPUT')
    rows = snapshot.get('positions', [])
    times = {r.get('time') for r in rows}
    if len(times) != 1 or None in times:
        fail('INTRADAY_BASELINE_TIME_UNAVAILABLE')
    baseline = stamp(next(iter(times)))
    if baseline.date().isoformat() != date:
        fail('INTRADAY_BASELINE_DATE_MISMATCH')
    positions = {}
    for row in rows:
        if row.get('asset_type') not in ('股票', '基金') or row.get('side') != '多':
            fail('INTRADAY_UNSUPPORTED_ASSET')
        code = row.get('code')
        if not re.fullmatch(r'\d{6}\.(?:XSHG|XSHE)', str(code)):
            fail('INTRADAY_INVALID_CODE')
        item = positions.setdefault(code, {'code': code, 'name': row['name'],
            'baseline_quantity': 0, 'quantity': 0, 'bought': 0, 'sold': 0})
        if item['name'] != row['name']:
            fail('INTRADAY_NAME_MISMATCH')
        qty = shares(row['amount'])
        item['quantity'] += qty
        item['baseline_quantity'] += qty
    cash = number(snapshot.get('cash'))
    seen = set()
    fills = []
    for row in transactions['transactions']:
        if row['side'] not in ('买', '卖'):
            fail('INTRADAY_UNSUPPORTED_TRANSACTION')
        if not row['filled_quantity']:
            continue
        # Cumulative partial fills may span the baseline; never guess the delta.
        if row['status'] != '全部成交' or row['filled_quantity'] != row['order_quantity']:
            fail('INTRADAY_PARTIAL_FILL_UNSUPPORTED')
        matched = stamp(row['match_time'])
        ordered = stamp(row['order_time'])
        if matched.date().isoformat() != date or matched < ordered:
            fail('INTRADAY_AMBIGUOUS_REPLAY_BOUNDARY')
        if matched < baseline:
            continue  # Already reflected in the timestamped snapshot.
        if ordered <= baseline:
            fail('INTRADAY_AMBIGUOUS_REPLAY_BOUNDARY')
        identity = tuple((k, str(v)) for k, v in sorted(row.items()))
        if identity in seen:
            fail('INTRADAY_DUPLICATE_FILL_WITHOUT_ID')
        seen.add(identity)
        fills.append(row)
    for row in sorted(fills, key=lambda r: r['match_time']):
        code, qty = row['code'], row['filled_quantity']
        item = positions.setdefault(code, {'code': code, 'name': row['name'],
            'baseline_quantity': 0, 'quantity': 0, 'bought': 0, 'sold': 0})
        if item['name'] != row['name']:
            fail('INTRADAY_NAME_MISMATCH')
        buying = row['side'] == '买'
        item['quantity'] += qty if buying else -qty
        item['bought' if buying else 'sold'] += qty
        cash += (-1 if buying else 1) * number(row['filled_value']) - number(row['commission'])
        if item['quantity'] < 0:
            fail('INTRADAY_NEGATIVE_HOLDINGS')
    if cash < 0:
        fail('INTRADAY_NEGATIVE_CASH')
    result = [dict(r, amount=f"{r['quantity']}股", closeable_amount=None,
                   price=None, value=None, weight=None) for r in positions.values() if r['quantity']]
    return {'id': snapshot['id'], 'date': date, 'source': 'snapshot_plus_confirmed_transactions',
        'baseline_time': baseline.isoformat(sep=' '), 'queried_at': transactions['queried_at'],
        'latest_fill_time': max((r['match_time'] for r in fills), default=None),
        'complete': True, 'position_count': len(result), 'positions': result,
        'cash': None, 'reconstructed_cash': float(cash), 'total_value': None,
        'valuation_status': 'unavailable', 'applied_fill_count': len(fills),
        'warnings': ['QUANTITIES_RECONSTRUCTED_FROM_API_EVIDENCE',
                     'CASH_ASSUMES_NO_OTHER_CASH_FLOWS', 'LIVE_VALUATION_UNAVAILABLE']}


def _get_page_holdings(client, live_id, *, date=None, limit=1000, name=None):
    date = selected_date(date)
    page = read_live_page(live_id, name)
    raw = page['positions']['rows']
    if page['positions']['records'] != len(raw) or len(raw) > limit:
        fail('INTRADAY_INCOMPLETE_INPUT')
    cash = re.sub(r'[￥¥,\s]', '', page.get('cash') or '')
    snapshot = {'id': live_id, 'is_limit': False, 'cash': cash,
        'positions': [_normalize_position(row) for row in raw]}
    tx = transaction_rows(page, date, limit)
    result = reconstruct(snapshot, tx)
    result.update(source='live_page_snapshot_plus_confirmed_transactions',
        page_name=page['name'], page_url=page['url'], transactions=tx['transactions'])
    result['warnings'][0] = 'QUANTITIES_RECONSTRUCTED_FROM_PAGE_TABLES'
    return result


def get_live_holdings(client, live_id, *, date=None, limit=1000, name=None, source='api'):
    """Read API snapshots and complete fills without starting or contacting Chrome."""
    if source == 'page':
        return _get_page_holdings(client, live_id, date=date, limit=limit, name=name)
    if source != 'api':
        raise UsageError('source must be api or page')
    date = selected_date(date)
    first = get_live_positions(client, live_id, date=date, limit=limit)
    tx = get_live_transactions(client, live_id, date=date, limit=limit, name=name)
    second = get_live_positions(client, live_id, date=date, limit=limit)
    final_tx = get_live_transactions(client, live_id, date=date, limit=limit, name=name)
    def signature(snapshot):
        return json.dumps({'positions': snapshot.get('positions'), 'cash': snapshot.get('cash'),
                           'is_limit': snapshot.get('is_limit')}, sort_keys=True, ensure_ascii=False)
    if signature(first) != signature(second) or tx['transactions'] != final_tx['transactions']:
        fail('INTRADAY_SOURCE_CHANGED_DURING_READ')
    result = reconstruct(second, final_tx)
    result.update(source='live_api_snapshot_plus_confirmed_transactions',
        transactions=final_tx['transactions'], transport='http', browser_required=False,
        read_consistency='two_matching_snapshots_and_transaction_reads',
        transaction_completeness=final_tx['completeness'])
    return result
