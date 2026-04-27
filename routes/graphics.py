from flask import Blueprint, render_template, jsonify
from storage import JSONStorage
import requests
import time
import math as _m

bp = Blueprint("graphics", __name__, template_folder="../templates")
import os as _os
_storage = None

def _get_storage():
    global _storage
    if _storage is None:
        _storage = JSONStorage(data_dir=_os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "data"))
    return _storage

def _parse_date(date_str):
    parts = date_str.split("-")
    return time.mktime((int(parts[0]), int(parts[1]), int(parts[2]), 0, 0, 0, 0, 0, 0))

def calc_deviation(entry_price, current_price):
    diff = current_price - entry_price
    pct = (diff / entry_price) * 100
    return diff, pct

def _round_disp(val, decimals=2):
    """Smart rounding for display - minimal significant digits"""
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

def _round_pct(val):
    """Round percentage"""
    if val is None or val == 0:
        return 0
    return round(val, 2)

def _round_usdt(val):
    """Round USDT - keep precision for small values"""
    if val is None or val == 0:
        return 0
    if abs(val) < 0.01:
        return round(val, 6)
    return round(val, 2)

@bp.route("/graphics/all")
def all_charts():
    storage = _get_storage()
    objects = storage.list()
    return render_template("graphics/all.html", objects=objects)

@bp.route("/graphics/chart/<obj_id>")
def chart(obj_id):
    storage = _get_storage()
    try:
        obj = storage.load(obj_id)
    except FileNotFoundError:
        return jsonify({"error": "Object not found"}), 404

    data = obj.data or {}
    emoji_entry = data.get("emoji_entry", {})

    symbol = emoji_entry.get("symbol", data.get("symbol", "FIL"))
    entry_price = emoji_entry.get("entry_price", data.get("entry_price"))
    entry_date = emoji_entry.get("entry_date", data.get("entry_date"))

    if not entry_price or not entry_date:
        return jsonify({"error": "Missing entry_price or entry_date"}), 400

    symbol_bitget = symbol.upper()
    if "/" in symbol_bitget:
        symbol_bitget = symbol_bitget.replace("/", "")

    try:
        entry_ts = _parse_date(entry_date)
        now_ts = int(time.time())
        diff_secs = now_ts - entry_ts
        if diff_secs < 0:
            limit = 1
        else:
            limit = min(1000, max(1, int(diff_secs / 86400) + 1))
        url = "https://api.bitget.com/api/v2/spot/market/candles?symbol=" + symbol_bitget + "USDT&granularity=1day&limit=" + str(limit) + "&startTime=" + str(int(entry_ts * 1000))
        resp = requests.get(url, timeout=3)
        api_data = resp.json()
        if api_data.get("code") != "00000":
            raise Exception("API error: " + api_data.get("msg"))
        candles = api_data.get("data", [])
        if not candles:
            raise Exception("No candles returned")
        ohlcv = []
        for c in candles:
            ohlcv.append([int(c[0]), float(c[1]), float(c[2]), float(c[3]), float(c[4]), float(c[5])])
        entry_ts_ms = int(entry_ts * 1000)
        ohlcv = [c for c in ohlcv if c[0] >= entry_ts_ms]
        if not ohlcv:
            raise Exception("No candles on or after " + entry_date)
        current_price = ohlcv[-1][4]
    except requests.Timeout:
        return jsonify({"error": "Timeout"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    points = []
    deviations_usdt = []
    deviations_pct = []
    max_high = 0
    max_low = float("inf")
    leverage = data.get("leverage", 10)
    volume = emoji_entry.get("volume", 1)

    for candle in ohlcv:
        ts, o, h, l, c, v = candle
        dt_val = time.strftime("%Y-%m-%d", time.gmtime(ts / 1000))
        diff_usdt, diff_pct = calc_deviation(entry_price, c)
        deviations_usdt.append(diff_usdt)
        deviations_pct.append(diff_pct)
        is_profitable = c > entry_price
        points.append({"date": dt_val, "close": _round_usdt(c), "deviation_usdt": _round_usdt(diff_usdt), "deviation_percent": _round_pct(diff_pct), "profitable": is_profitable})
        if h > max_high:
            max_high = h
        if l < max_low:
            max_low = l

    diff_usdt, diff_pct = calc_deviation(entry_price, current_price)
    max_usdt = max_high - entry_price
    min_usdt = max_low - entry_price
    max_pct = (max_high - entry_price) / entry_price * 100
    min_pct = (max_low - entry_price) / entry_price * 100
    max_usdt_leveraged = max_usdt * leverage
    min_usdt_leveraged = min_usdt * leverage
    max_pct_leveraged = max_pct * leverage
    min_pct_leveraged = min_pct * leverage
    max_usdt_with_volume = max_usdt / volume
    min_usdt_with_volume = min_usdt / volume
    max_usdt_leveraged_volume = max_usdt_leveraged / volume
    min_usdt_leveraged_volume = min_usdt_leveraged / volume
    body = abs(current_price - entry_price)
    body_pct = _round_pct(body / entry_price * 100)
    upper_wick = max_high - max(entry_price, current_price)
    lower_wick = min(entry_price, current_price) - max_low
    volatility = max_high - max_low
    entry_time_calc = int((time.time() - _parse_date(entry_date)) / 86400)
    bubble = diff_pct * leverage
    pnl_usdt = round(bubble, 2) / volume
    emoji_upd = {"current_price": _round_usdt(current_price), "entry_time": entry_time_calc, "pnl_percent": _round_pct(diff_pct), "pnl_percent_leveraged": _round_pct(bubble), "pnl_usdt": _round_usdt(pnl_usdt), "result": "🟢" if pnl_usdt > 0 else "🔴"}
    ohlc = {"current": {"high": _round_usdt(max_high), "low": _round_usdt(max_low), "body": _round_usdt(body), "body_pct": body_pct, "upper_wick": _round_usdt(upper_wick), "lower_wick": _round_usdt(lower_wick), "pct": _round_pct(diff_pct), "pct_x": _round_pct(diff_pct * leverage)}, "max": {"price": _round_usdt(max_high), "pct": _round_pct((max_high - entry_price) / entry_price * 100), "pct_x": _round_pct((max_high - entry_price) / entry_price * 100 * leverage), "volatility": _round_usdt(volatility)}, "min": {"price": _round_usdt(max_low), "pct": _round_pct((max_low - entry_price) / entry_price * 100), "pct_x": _round_pct((max_low - entry_price) / entry_price * 100 * leverage), "volatility": _round_usdt(volatility)}}
    dn = sum(1 for c in ohlcv if c[4] < entry_price)
    dp = sum(1 for c in ohlcv if c[4] > entry_price)
    dn_equal = sum(1 for c in ohlcv if c[4] == entry_price)
    da = len(ohlcv)
    stats = {"dn": dn, "dp": dp, "dn_equal": dn_equal, "da": da}
    summary = {"symbol": symbol, "entry_price": entry_price, "entry_date": entry_date, "current_price": _round_usdt(current_price), "total_deviation_usdt": _round_usdt(diff_usdt), "total_deviation_percent": _round_pct(diff_pct), "profitable": current_price > entry_price, "max_usdt": _round_usdt(max_usdt), "min_usdt": _round_usdt(min_usdt), "max_pct": _round_pct(max_pct), "min_pct": _round_pct(min_pct), "max_usdt_leveraged": _round_usdt(max_usdt_leveraged), "min_usdt_leveraged": _round_usdt(min_usdt_leveraged), "max_pct_leveraged": _round_pct(max_pct_leveraged), "min_pct_leveraged": _round_pct(min_pct_leveraged), "max_usdt_with_volume": _round_usdt(max_usdt_with_volume), "min_usdt_with_volume": _round_usdt(min_usdt_with_volume), "max_usdt_leveraged_volume": _round_usdt(max_usdt_leveraged_volume), "min_usdt_leveraged_volume": _round_usdt(min_usdt_leveraged_volume), "leverage": leverage, "volume": volume}
    try:
        obj = storage.load(obj_id)
        obj.data["emoji_upd"] = emoji_upd
        obj.data["ohlc"] = ohlc
        obj.data["stats"] = stats
        obj.data["chart_updated"] = time.strftime("%Y-%m-%d %H:%M")
        storage.save(obj)
    except Exception:
        pass
    return jsonify({"chart": points, "summary": summary, "emoji_upd": emoji_upd, "ohlc": ohlc, "stats": stats})
