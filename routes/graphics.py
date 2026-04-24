from flask import Blueprint, render_template, jsonify
from storage import JSONStorage
import ccxt
from datetime import datetime, timedelta
import math

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


@bp.route('/graphics')
def index():
    return render_template('graphics/index.html')


@bp.route('/graphics/chart/<obj_id>')
def chart(obj_id):
    storage = _get_storage()
    try:
        obj = storage.load(obj_id)
    except FileNotFoundError:
        return jsonify({'error': 'Object not found'}), 404

    data = obj.data or {}
    symbol = data.get('symbol', 'FIL/USDT')
    entry_price = data.get('entry_price')
    entry_date = data.get('entry_date')

    if not entry_price or not entry_date:
        return jsonify({'error': 'Missing entry_price or entry_date'}), 400

    symbol_ccxt = symbol.replace('FIL', 'FIL/USDT').replace('ATOM', 'ATOM/USDT').replace('CAKE', 'CAKE/USDT').replace('API3', 'API3/USDT')
    if '/' not in symbol_ccxt:
        symbol_ccxt = symbol_ccxt + '/USDT'

    try:
        exchange = ccxt.bitget()
        since_ts = int(datetime.strptime(entry_date, '%Y-%m-%d').timestamp() * 1000)
        now_ts = int(datetime.now().timestamp() * 1000)
        ohlcv = exchange.fetch_ohlcv(symbol_ccxt, '1d', since=since_ts, limit=500)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    current = exchange.fetch_ticker(symbol_ccxt)
    current_price = current['last']

    points = []
    deviations_usdt = []
    deviations_pct = []
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

    diff_usdt, diff_pct = calc_deviation(entry_price, current_price)
    max_usdt = round(max(deviations_usdt), 2)
    min_usdt = round(min(deviations_usdt), 2)
    max_pct = round(max(deviations_pct), 2)
    min_pct = round(min(deviations_pct), 2)

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
        obj.data['chart_max_usdt'] = max_usdt
        obj.data['chart_min_usdt'] = min_usdt
        obj.data['chart_max_pct'] = max_pct
        obj.data['chart_min_pct'] = min_pct
        obj.data['chart_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M')
        storage.save(obj)
    except Exception:
        pass

    return jsonify({'chart': points, 'summary': summary})
