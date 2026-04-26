from flask import Blueprint, render_template, jsonify
from storage import JSONStorage
import requests
from datetime import datetime, timedelta
import math
import time

bp = Blueprint('graphics', __name__, template_folder='../templates')
import os as _os
_storage = None

def _get_storage():
    global _storage
    if _storage is None:
        _storage = JSONStorage(data_dir=_os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), 'data'))
    return _storage


def calc_deviation(entry_price, current_price):
    diff = current_price - entry_price
    pct = (diff / entry_price) * 100
    return round(diff, 6), round(pct, 4)


@bp.route('/graphics/all')
def all_charts():
    storage = _get_storage()
    objects = storage.list()
    return render_template('graphics/all.html', objects=objects)


@bp.route('/graphics/chart/<obj_id>')
def chart(obj_id):
    storage = _get_storage()
    try:
        obj = storage.load(obj_id)
    except FileNotFoundError:
        return jsonify({'error': 'Object not found'}), 404

    data = obj.data or {}
    emoji_entry = data.get('emoji_entry', {})

    symbol = emoji_entry.get('symbol', data.get('symbol', 'FIL'))
    entry_price = emoji_entry.get('entry_price', data.get('entry_price'))
    entry_date = emoji_entry.get('entry_date', data.get('entry_date'))

    if not entry_price or not entry_date:
        return jsonify({'error': 'Missing entry_price or entry_date'}), 400

    symbol_bitget = symbol.upper()
    if '/' in symbol_bitget:
        symbol_bitget = symbol_bitget.replace('/', '')

    try:
        start_ts = int(datetime.strptime(entry_date, '%Y-%m-%d').timestamp() * 1000)
        limit = min(90, max(1, int((datetime.now() - datetime.strptime(entry_date, '%Y-%m-%d')).days) + 1))
        
        url = f'https://api.bitget.com/api/v2/spot/market/candles?symbol={symbol_bitget}USDT&granularity=1day&limit={limit}&startTime={start_ts}'
        resp = requests.get(url, timeout=3)
        data = resp.json()
        if data.get('code') != '00000':
            raise Exception(f"API error: {data.get('msg')}")
        candles = data.get('data', [])
        if not candles:
            raise Exception("No candles returned")
        ohlcv = [[int(c[0]), float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5])] for c in candles]
        current_price = ohlcv[-1][4]
    except requests.Timeout:
        return jsonify({'error': 'Timeout'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    points = []
    deviations_usdt = []
    deviations_pct = []
    max_high = 0
    max_low = float('inf')

    for candle in ohlcv:
        ts, o, h, l, c, v = candle
        dt = datetime.utcfromtimestamp(ts / 1000).strftime('%Y-%m-%d')
        diff_usdt, diff_pct = calc_deviation(entry_price, c)
        deviations_usdt.append(diff_usdt)
        deviations_pct.append(diff_pct)
        is_profitable = c > entry_price
        points.append({
            'date': dt,
            'close': round(c, 6),
            'deviation_usdt': diff_usdt,
            'deviation_percent': diff_pct,
            'profitable': is_profitable
        })
        if h > max_high:
            max_high = h
        if l < max_low:
            max_low = l

    diff_usdt, diff_pct = calc_deviation(entry_price, current_price)
    max_usdt = round(max(deviations_usdt), 2)
    min_usdt = round(min(deviations_usdt), 2)
    max_pct = round(max(deviations_pct), 2)
    min_pct = round(min(deviations_pct), 2)

    body = round(abs(current_price - entry_price), 6)
    body_pct = round((body / entry_price) * 100, 4)
    upper_wick = round(max_high - max(entry_price, current_price), 6)
    lower_wick = round(min(entry_price, current_price) - max_low, 6)
    volatility = round(max_high - max_low, 6)

    entry_time_calc = (datetime.now() - datetime.strptime(entry_date, '%Y-%m-%d')).days
    emoji_upd = {
        'current_price': round(current_price, 6),
        'entry_time': entry_time_calc,
        'pnl_percent': round(diff_pct, 2),
        'pnl_usdt': round(diff_usdt, 2)
    }

    ohlc = {
        'current': {
            'high': round(max_high, 6),
            'low': round(max_low, 6),
            'body': body,
            'body_pct': body_pct,
            'upper_wick': upper_wick,
            'lower_wick': lower_wick,
            'pct': diff_pct,
            'pct_x': round(diff_pct * 10, 2)
        },
        'max': {
            'price': round(max_high, 6),
            'pct': round((max_high - entry_price) / entry_price * 100, 2),
            'pct_x': round((max_high - entry_price) / entry_price * 100 * 10, 2),
            'volatility': volatility
        },
        'min': {
            'price': round(max_low, 6),
            'pct': round((max_low - entry_price) / entry_price * 100, 2),
            'pct_x': round((max_low - entry_price) / entry_price * 100 * 10, 2),
            'volatility': volatility
        }
    }

    leverage = data.get('leverage', 10)
    dn = math.ceil(max_low / leverage) if max_low else 0
    dp = math.ceil(max_high / leverage) if max_high else 0
    da = int(entry_price / leverage) if entry_price else 0

    stats = {
        'dn': dn,
        'dp': dp,
        'da': da
    }

    summary = {
        'symbol': symbol,
        'entry_price': entry_price,
        'entry_date': entry_date,
        'current_price': round(current_price, 6),
        'total_deviation_usdt': round(diff_usdt, 2),
        'total_deviation_percent': round(diff_pct, 2),
        'profitable': current_price > entry_price,
        'max_usdt': max_usdt,
        'min_usdt': min_usdt,
        'max_pct': max_pct,
        'min_pct': min_pct
    }

    try:
        obj = storage.load(obj_id)
        obj.data['emoji_upd'] = emoji_upd
        obj.data['ohlc'] = ohlc
        obj.data['stats'] = stats
        obj.data['chart_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M')
        storage.save(obj)
    except Exception:
        pass

    return jsonify({'chart': points, 'summary': summary, 'emoji_upd': emoji_upd, 'ohlc': ohlc, 'stats': stats})