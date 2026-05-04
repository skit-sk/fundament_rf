import re
import time
import uuid
import requests
from threading import Thread
from datetime import datetime
from flask import Blueprint, request, jsonify, render_template
from storage import get_storage, get_metrics_storage

bp = Blueprint('processor_1d', __name__, url_prefix='/processor_1d')
storage = get_storage()
metrics_storage = get_metrics_storage()

TIMEOUT = 5
RETRIES = 3


def _parse_date(date_str):
    parts = date_str.split("-")
    return time.mktime((int(parts[0]), int(parts[1]), int(parts[2]), 0, 0, 0, 0, 0, 0))


def _round_disp(val, decimals=2):
    if val is None:
        return 0
    if abs(val) < 0.000001 and val != 0:
        return val
    if val == 0:
        return 0
    if abs(val) >= 10:
        return round(val, decimals)
    if abs(val) >= 1:
        return round(val, max(decimals, 2))
    return round(val, 6)


def _fetch_with_retry(url, retries=RETRIES, timeout=TIMEOUT):
    last_error = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=timeout)
            if resp.status_code == 200:
                return resp
        except Exception as e:
            last_error = e
            if attempt < retries - 1:
                time.sleep(0.5)
    raise Exception(f"Failed after {retries} attempts: {last_error}")


def _fetch_candles(symbol, start_ts, end_ts):
    symbol = symbol.upper().replace("/", "")
    limit = min(1000, max(1, int((end_ts - start_ts) / 86400) + 1))
    url = f"https://api.bitget.com/api/v2/spot/market/candles?symbol={symbol}USDT&granularity=1day&limit={limit}&startTime={int(start_ts * 1000)}"
    resp = _fetch_with_retry(url)
    api_data = resp.json()
    if api_data.get("code") != "00000":
        raise Exception("API error: " + api_data.get("msg"))
    candles = api_data.get("data", [])
    return candles


def _calculate_day(candle, entry_price, leverage, volume, prev_volatility=None):
    ts, o, h, l, c, v = [float(x) for x in candle[:6]]
    dt_val = time.strftime("%Y-%m-%d", time.gmtime(int(ts) / 1000))

    body = abs(c - o)
    body_pct = (body / o * 100) if o != 0 else 0
    upper_wick = h - max(o, c)
    lower_wick = min(o, c) - l

    deviation_from_entry_pct = ((c - entry_price) / entry_price * 100) if entry_price != 0 else 0
    deviation_from_entry_usdt = c - entry_price
    deviation_from_open_usdt = c - o
    deviation_from_open_pct = ((c - o) / o * 100) if o != 0 else 0

    volatility = h - l
    roe_pct = deviation_from_entry_pct * leverage
    pnl_usdt = roe_pct * volume / 100
    profitable = roe_pct > 0

    return {
        "date": dt_val,
        "ohlc": {
            "open": round(o, 6),
            "high": round(h, 6),
            "low": round(l, 6),
            "close": round(c, 6),
            "body": round(body, 6),
            "body_pct": round(body_pct, 2),
            "upper_wick": round(upper_wick, 6),
            "lower_wick": round(lower_wick, 6)
        },
        "deviation": {
            "from_entry_usdt": round(deviation_from_entry_usdt, 6),
            "from_entry_pct": round(deviation_from_entry_pct, 2),
            "from_open_usdt": round(deviation_from_open_usdt, 6),
            "from_open_pct": round(deviation_from_open_pct, 2)
        },
        "roe_pct": round(roe_pct, 2),
        "pnl_usdt": round(pnl_usdt, 4),
        "volatility": round(volatility, 6),
        "profitable": profitable
    }


def _calculate_summary(days, leverage, volume):
    total = len(days)
    if total == 0:
        return {}
    profitable_days = sum(1 for d in days if d['profitable'])
    loss_days = sum(1 for d in days if d['roe_pct'] < 0)
    neutral_days = sum(1 for d in days if d['roe_pct'] == 0)
    avg_roe = sum(d['roe_pct'] for d in days) / total
    avg_vol = sum(d['volatility'] for d in days) / total

    last = days[-1]
    current_roe = last['roe_pct']
    current_pnl = last['pnl_usdt']

    max_profit_day = max(days, key=lambda x: x['roe_pct'])
    max_loss_day = min(days, key=lambda x: x['roe_pct'])

    max_drawdown = min(d['deviation']['from_entry_pct'] for d in days)
    max_drawdown_usdt = min(d['deviation']['from_entry_usdt'] for d in days)

    streak_profit = 0
    streak_loss = 0
    current_streak = 0
    streak_type = None
    for d in days:
        if d['profitable']:
            if streak_type == 'profit':
                current_streak += 1
            else:
                current_streak = 1
                streak_type = 'profit'
            streak_profit = max(streak_profit, current_streak)
        else:
            if streak_type == 'loss':
                current_streak += 1
            else:
                current_streak = 1
                streak_type = 'loss'
            streak_loss = max(streak_loss, current_streak)

    return {
        "total_days": total,
        "profitable_days": profitable_days,
        "loss_days": loss_days,
        "neutral_days": neutral_days,
        "current_roe_pct": round(current_roe, 2),
        "current_pnl_usdt": round(current_pnl, 4),
        "avg_roe_pct": round(avg_roe, 2),
        "avg_volatility": round(avg_vol, 6),
        "max_profit_day": {"date": max_profit_day['date'], "roe_pct": max_profit_day['roe_pct'], "pnl_usdt": max_profit_day['pnl_usdt']},
        "max_loss_day": {"date": max_loss_day['date'], "roe_pct": max_loss_day['roe_pct'], "pnl_usdt": max_loss_day['pnl_usdt']},
        "max_drawdown_pct": round(max_drawdown, 2),
        "max_drawdown_usdt": round(max_drawdown_usdt, 6),
        "streak_profit": streak_profit,
        "streak_loss": streak_loss
    }


def _build_chart_data(days):
    return [{"date": d['date'], "deviation_pct": d['deviation']['from_entry_pct'], "profitable": d['profitable']} for d in days]


def _calculate_ranges(days_data, entry_price, current_price, low_price, high_price):
    if not days_data:
        return {}

    roe_list = [d['roe_pct'] for d in days_data]

    def calc_pct(price1, price2):
        return round(price2 - price1, 6)

    def calc_prc(price1, price2):
        if price1 == 0:
            return 0
        return round(((price2 - price1) / price1) * 100, 2)

    def calc_days_in_range(price_key):
        if price_key == 'entry_current':
            target_low, target_high = entry_price, current_price
        elif price_key == 'entry_low':
            target_low, target_high = low_price, entry_price
        elif price_key == 'entry_high':
            target_low, target_high = entry_price, high_price
        elif price_key == 'current_low':
            target_low, target_high = low_price, current_price
        elif price_key == 'current_high':
            target_low, target_high = current_price, high_price
        elif price_key == 'low_high':
            target_low, target_high = low_price, high_price
        else:
            return 0

        count = 0
        for d in days_data:
            close = d['ohlc']['close']
            if target_low <= close <= target_high:
                count += 1
        return count

    def calc_shortest_days(start_idx, target_price, direction):
        if start_idx >= len(days_data):
            return 0

        for i in range(start_idx + 1, len(days_data)):
            curr_price = days_data[i]['ohlc']['close']
            if direction > 0:
                if curr_price >= target_price:
                    return i - start_idx
            else:
                if curr_price <= target_price:
                    return i - start_idx

        return 0

    entry_idx = 0
    current_idx = len(days_data) - 1

    ranges = {
        "entry_current": {
            "pct": calc_pct(entry_price, current_price),
            "prc": calc_prc(entry_price, current_price),
            "days": calc_days_in_range('entry_current'),
            "shortest_days": calc_shortest_days(entry_idx, current_price, 1)
        },
        "entry_low": {
            "pct": calc_pct(entry_price, low_price),
            "prc": calc_prc(entry_price, low_price),
            "days": calc_days_in_range('entry_low'),
            "shortest_days": calc_shortest_days(entry_idx, low_price, -1)
        },
        "entry_high": {
            "pct": calc_pct(entry_price, high_price),
            "prc": calc_prc(entry_price, high_price),
            "days": calc_days_in_range('entry_high'),
            "shortest_days": calc_shortest_days(entry_idx, high_price, 1)
        },
        "current_low": {
            "pct": calc_pct(current_price, low_price),
            "prc": calc_prc(current_price, low_price),
            "days": calc_days_in_range('current_low'),
            "shortest_days": calc_shortest_days(current_idx, low_price, -1)
        },
        "current_high": {
            "pct": calc_pct(current_price, high_price),
            "prc": calc_prc(current_price, high_price),
            "days": calc_days_in_range('current_high'),
            "shortest_days": calc_shortest_days(current_idx, high_price, 1)
        },
        "low_high": {
            "pct": calc_pct(low_price, high_price),
            "prc": calc_prc(low_price, high_price),
            "days": calc_days_in_range('low_high'),
            "shortest_days": calc_shortest_days(entry_idx, high_price, 1)
        }
    }

    return ranges


def _process_object(obj_id, operation='create'):
    timing = {
        "operation": operation,
        "obj_id": obj_id,
        "timestamp": datetime.now().isoformat(),
        "duration_ms": {}
    }

    symbol = 'UNKNOWN'

    try:
        obj = storage.load(obj_id)
        emoji_entry = obj.data.get('emoji_entry', {})
        symbol = emoji_entry.get('symbol', obj.data.get('symbol', 'UNKNOWN'))
        entry_price = float(emoji_entry.get('entry_price', obj.data.get('entry_price', 0)))
        entry_date = emoji_entry.get('entry_date', obj.data.get('entry_date'))
        leverage = obj.data.get('leverage', 10)
        volume = float(emoji_entry.get('volume', 1))

        if not entry_price or not entry_date:
            raise Exception("Missing entry_price or entry_date")

        start_ts = _parse_date(entry_date)
        end_ts = time.time()

        api_start = int(time.time() * 1000)
        candles = _fetch_candles(symbol, start_ts, end_ts)
        api_end = int(time.time() * 1000)

        raw_candles = []
        days_data = []
        for i, c in enumerate(candles):
            ts, o, h, l, ci, v = c[:6]
            raw_candles.append({
                "date": time.strftime("%Y-%m-%d", time.gmtime(int(ts) / 1000)),
                "timestamp_ms": int(ts),
                "open": float(o),
                "high": float(h),
                "low": float(l),
                "close": float(ci),
                "volume": float(v)
            })

        processing_start = int(time.time() * 1000)
        for i, candle in enumerate(candles):
            ts, o, h, l, ci, v = candle[:6]
            day = _calculate_day((ts, o, h, l, ci, v), entry_price, leverage, volume)
            day['day_index'] = i
            days_data.append(day)
        processing_end = int(time.time() * 1000)

        summary = _calculate_summary(days_data, leverage, volume)
        chart_data = _build_chart_data(days_data)

        last_day = days_data[-1] if days_data else None
        current_price = last_day['ohlc']['close'] if last_day else entry_price

        max_day = max(days_data, key=lambda x: x['ohlc']['high']) if days_data else None
        min_day = min(days_data, key=lambda x: x['ohlc']['low']) if days_data else None
        high_price = max_day['ohlc']['high'] if max_day else entry_price
        low_price = min_day['ohlc']['low'] if min_day else entry_price

        ranges = _calculate_ranges(days_data, entry_price, current_price, low_price, high_price)

        entry_datetime = f"{entry_date}T00:00:00"
        current_datetime = last_day['date'] + "T00:00:00" if last_day else None
        low_datetime = min_day['date'] + "T00:00:00" if min_day else None
        high_datetime = max_day['date'] + "T00:00:00" if max_day else None

        writing_start = int(time.time() * 1000)

        raw_data = {
            "id": f"{obj_id}_RAW",
            "parent_id": obj_id,
            "symbol": symbol.upper(),
            "granularity": "1day",
            "source": "bitget",
            "fetched_at": datetime.now().isoformat(),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "candles": raw_candles,
            "total_candles": len(raw_candles)
        }
        storage.save_raw(symbol, obj_id, raw_data)

        d1_data = {
            "id": f"{obj_id}_1D",
            "parent_id": obj_id,
            "symbol": symbol.upper(),
            "entry_price": entry_price,
            "entry_date": entry_date,
            "leverage": leverage,
            "volume": volume,
            "status": "completed",
            "fetched_at": datetime.now().isoformat(),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "days": days_data,
            "chart_data": chart_data,
            "summary": summary
        }
        storage.save_1d(symbol, obj_id, d1_data)

        obj.data['entry_datetime'] = entry_datetime
        obj.data['current_datetime'] = current_datetime
        obj.data['low_datetime'] = low_datetime
        obj.data['high_datetime'] = high_datetime
        obj.data['ranges'] = ranges
        obj.data['chart_updated'] = datetime.now().strftime("%Y-%m-%d %H:%M")
        storage.save_to_card(obj)
        storage.save(obj)

        writing_end = int(time.time() * 1000)

        timing['duration_ms'] = {
            "api_request_start": api_start,
            "api_request_end": api_end,
            "api_request_ms": api_end - api_start,
            "processing_start": processing_start,
            "processing_end": processing_end,
            "processing_ms": processing_end - processing_start,
            "writing_start": writing_start,
            "writing_end": writing_end,
            "writing_ms": writing_end - writing_start,
            "total_ms": writing_end - api_start
        }
        timing['result'] = {
            "status": "completed",
            "days_processed": len(days_data),
            "added": 0,
            "changed": 0,
            "skipped": 0
        }

    except Exception as e:
        timing['result'] = {"status": "failed", "error": str(e)}
        try:
            d1_error = {"status": "failed", "error": str(e)}
            storage.save_1d(symbol, obj_id, d1_error)
        except Exception:
            pass

    metrics_storage.add_record(timing)
    return timing


def _sync_object(obj_id):
    timing = {
        "operation": "sync",
        "obj_id": obj_id,
        "timestamp": datetime.now().isoformat(),
        "duration_ms": {}
    }

    try:
        obj = storage.load(obj_id)
        symbol = obj.data.get('emoji_entry', {}).get('symbol', 'UNKNOWN')

        if obj.data.get('ranges'):
            timing['duration_ms'] = {"total_ms": 0}
            timing['result'] = {"status": "skipped", "reason": "ranges already exist"}
            metrics_storage.add_record(timing)
            return timing

        chart_updated = obj.data.get('chart_updated')

        if storage.exists_1d(symbol, obj_id):
            d1_data = storage.load_1d(symbol, obj_id)
            d1_updated = d1_data.get('updated_at')

            if chart_updated and d1_updated and chart_updated == d1_updated:
                timing['duration_ms'] = {"total_ms": 0}
                timing['result'] = {"status": "skipped", "reason": "chart_updated equals d1_updated"}
                metrics_storage.add_record(timing)
                return timing

        result = _process_object(obj_id, 'sync')
        result['result']['skipped'] = 1
        return result

    except Exception as e:
        timing['result'] = {"status": "failed", "error": str(e)}
        metrics_storage.add_record(timing)
        return timing


def _force_object(obj_id):
    return _process_object(obj_id, 'force')


@bp.route('/create/<obj_id>', methods=['POST'])
def create_1d(obj_id):
    thread = Thread(target=_process_object, args=(obj_id, 'create'))
    thread.start()
    return jsonify({"status": "processing", "obj_id": obj_id}), 202


@bp.route('/sync/<obj_id>', methods=['POST'])
def sync_1d(obj_id):
    thread = Thread(target=_sync_object, args=(obj_id,))
    thread.start()
    return jsonify({"status": "syncing", "obj_id": obj_id}), 202


@bp.route('/force/<obj_id>', methods=['POST'])
def force_1d(obj_id):
    thread = Thread(target=_force_object, args=(obj_id,))
    thread.start()
    return jsonify({"status": "processing", "obj_id": obj_id}), 202


@bp.route('/status/<obj_id>', methods=['GET'])
def status(obj_id):
    status_data = {"obj_id": obj_id}
    try:
        obj = storage.load(obj_id)
        symbol = obj.data.get('emoji_entry', {}).get('symbol', 'UNKNOWN')
        status_data['d1_exists'] = storage.exists_1d(symbol, obj_id)
        status_data['raw_exists'] = storage.exists_raw(symbol, obj_id)
        if storage.exists_1d(symbol, obj_id):
            d1 = storage.load_1d(symbol, obj_id)
            status_data['d1_status'] = d1.get('status', 'unknown')
            status_data['d1_updated'] = d1.get('updated_at')
        status_data['main_updated'] = obj.data.get('chart_updated')
        return jsonify(status_data)
    except FileNotFoundError:
        return jsonify({"error": "Object not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/data/<obj_id>', methods=['GET'])
def get_data(obj_id):
    try:
        obj = storage.load(obj_id)
        symbol = obj.data.get('emoji_entry', {}).get('symbol', 'UNKNOWN')
        data = storage.load_1d(symbol, obj_id)
        return jsonify(data)
    except FileNotFoundError:
        return jsonify({"error": "1D data not found"}), 404


@bp.route('/raw/<obj_id>', methods=['GET'])
def get_raw(obj_id):
    try:
        obj = storage.load(obj_id)
        symbol = obj.data.get('emoji_entry', {}).get('symbol', 'UNKNOWN')
        data = storage.load_raw(symbol, obj_id)
        return jsonify(data)
    except FileNotFoundError:
        return jsonify({"error": "RAW data not found"}), 404


@bp.route('/delete/<obj_id>', methods=['DELETE'])
def delete_1d_raw(obj_id):
    try:
        obj = storage.load(obj_id)
        symbol = obj.data.get('emoji_entry', {}).get('symbol', 'UNKNOWN')
        storage.delete_1d_raw(symbol, obj_id)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route('/batch', methods=['POST'])
def batch_process():
    obj_ids = request.json.get('obj_ids', [])
    if not obj_ids:
        return jsonify({"error": "No obj_ids provided"}), 400

    results = []
    for obj_id in obj_ids:
        result = _process_object(obj_id, 'batch')
        results.append(result)

    return jsonify({
        "processed": len(obj_ids),
        "results": results
    })


@bp.route('/metrics', methods=['GET'])
def metrics_page():
    return render_template('metrics.html')


@bp.route('/metrics/data', methods=['GET'])
def metrics_data():
    data = metrics_storage.load()
    return jsonify(data)


@bp.route('/metrics/clear', methods=['POST'])
def metrics_clear():
    metrics_storage.clear()
    return jsonify({"ok": True})


@bp.route('/chart/<obj_id>', methods=['GET'])
def get_chart_data(obj_id):
    """Возвращает days для OHLC графика"""
    try:
        obj = storage.load(obj_id)
        symbol = obj.data.get('emoji_entry', {}).get('symbol', 'UNKNOWN')
        data = storage.load_1d(symbol, obj_id)
        return jsonify({
            'days': data.get('days', []),
            'symbol': data.get('symbol'),
            'entry_price': data.get('entry_price')
        })
    except FileNotFoundError:
        return jsonify({'error': 'No data file'}), 404