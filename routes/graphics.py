from flask import Blueprint, render_template, jsonify
from storage import get_storage
import requests
import time
import math as _m
from datetime import datetime

bp = Blueprint("graphics", __name__, template_folder="../templates")

def _get_storage():
    return get_storage()

def _get_1m_price(symbol):
    """Получить текущую цену из 1-минутной свечи"""
    url = f"https://api.bitget.com/api/v2/spot/market/candles?symbol={symbol}USDT&granularity=1min&limit=1"
    try:
        resp = requests.get(url, timeout=5)
        data = resp.json()
        if data.get("code") == "00000" and data.get("data"):
            return float(data["data"][0][4])
    except Exception:
        pass
    return None

def _get_daily_price(symbol):
    """Fallback — получить цену из дневной свечи"""
    url = f"https://api.bitget.com/api/v2/spot/market/candles?symbol={symbol}USDT&granularity=1day&limit=1"
    try:
        resp = requests.get(url, timeout=5)
        data = resp.json()
        if data.get("code") == "00000" and data.get("data"):
            return float(data["data"][0][4])
    except Exception:
        pass
    return None

def _get_current_price(symbol):
    """Получить текущую цену: сначала 1m, потом fallback на daily"""
    price = _get_1m_price(symbol)
    if price is None:
        price = _get_daily_price(symbol)
    return price

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

    chart_updated = data.get("chart_updated", "")[:10]
    today_str = time.strftime("%Y-%m-%d")

    points = []
    deviations_usdt = []
    deviations_pct = []
    max_high = 0
    max_low = float("inf")
    ohlcv = []
    current_price = None

    if chart_updated == today_str and data.get("chart"):
        existing_chart = data.get("chart", [])
        if existing_chart:
            current_price = _get_current_price(symbol_bitget)
            if current_price is None:
                current_price = float(entry_price)
            dp = 0
            dn = 0
            for p in existing_chart:
                c = p.get("close", entry_price)
                diff_usdt, diff_pct = calc_deviation(entry_price, c)
                deviations_usdt.append(diff_usdt)
                deviations_pct.append(diff_pct)
                if c > max_high:
                    max_high = c
                if c < max_low:
                    max_low = c
                if c > entry_price:
                    dp += 1
                elif c < entry_price:
                    dn += 1
                points.append(p)
            da = len(existing_chart)
            dn_equal = da - dp - dn
            stats = {"dn": dn, "dp": dp, "dn_equal": dn_equal, "da": da}
        else:
            chart_updated = ""
            current_price = float(entry_price)
    else:
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

    if current_price is None:
        current_price = float(entry_price)

    stats_defined = chart_updated == today_str and data.get("chart") and existing_chart

    leverage = data.get("leverage", 10)
    volume = emoji_entry.get("volume", 1)

    for candle in ohlcv:
        ts, o, h, l, c, v = candle
        dt_val = time.strftime("%Y-%m-%d", time.gmtime(ts / 1000))
        diff_usdt, diff_pct = calc_deviation(entry_price, c)
        deviations_usdt.append(diff_usdt)
        deviations_pct.append(diff_pct)
        is_profitable = c > entry_price
        points.append({"date": dt_val, "close": _round_usdt(c), "deviation_usdt": _round_usdt(diff_usdt), "deviation_percent": _round_pct(diff_pct), "profitable": is_profitable, "volume": v})
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
    
    # СТРОГО ПО ВВОДУ (emoji_entry):
    # 🧾entry_price, 🧱volume, 🫧pnl_percent, 🪙pnl_usdt
    entry_price_base = float(emoji_entry.get('entry_price', entry_price))
    volume_base = float(emoji_entry.get('volume', volume))
    leverage = data.get("leverage", 10)
    
    # Данные из ввода (сырые, БЕЗ плеча)
    input_pct = emoji_entry.get('pnl_percent')
    input_usdt = emoji_entry.get('pnl_usdt')
    
    # Текущая цена уже получена с биржи (строка 100) - НЕ перезаписываем!
    
    # 2. pnl_percent = изменение % БЕЗ leverage
    if current_price > 0 and entry_price_base > 0:
        pnl_pct_calc = (current_price / entry_price_base * 100) - 100
    else:
        pnl_pct_calc = 0.0
    
    # 3. ROE = (current - entry) × leverage × 100 (изменение цены × leverage)
    # pnl_usdt = ROE × volume / 100
    pnl_pct_lev = pnl_pct_calc * leverage
    pnl_usdt_calc = pnl_pct_lev * volume_base / 100
    roe_usdt = pnl_pct_lev / 100

    range_days = 0
    range_pct = 0
    entry_pct = 0
    current_pct = 0
    critical_levels = []

    if ohlcv and len(ohlcv) > 0:
        all_lows = [c[3] for c in ohlcv]
        all_highs = [c[2] for c in ohlcv]
        all_closes = [c[4] for c in ohlcv]
        all_volumes = [c[5] for c in ohlcv]
        all_timestamps = [c[0] for c in ohlcv]

        low_price = min(all_lows)
        high_price = max(all_highs)
        min_close_price = min(all_closes)
        max_close_price = max(all_closes)

        low_idx = all_lows.index(low_price)
        high_idx = all_highs.index(high_price)
        low_ts = all_timestamps[low_idx]
        high_ts = all_timestamps[high_idx]

        range_days = int(abs(high_ts - low_ts) / 86400000)
        range_pct = (high_price - low_price) / low_price * 100 if low_price > 0 else 0

        price_range = high_price - low_price
        if price_range > 0:
            entry_pct = (float(entry_price) - low_price) / price_range * 100
            current_pct = (current_price - low_price) / price_range * 100
        else:
            entry_pct = 50
            current_pct = 50

        min_vol_idx = all_volumes.index(min(all_volumes))
        max_vol_idx = all_volumes.index(max(all_volumes))
        min_vol_price = all_closes[min_vol_idx]
        max_vol_price = all_closes[max_vol_idx]
        min_vol = all_volumes[min_vol_idx]
        max_vol = all_volumes[max_vol_idx]
        min_vol_ts = all_timestamps[min_vol_idx]
        max_vol_ts = all_timestamps[max_vol_idx]
        min_vol_date = time.strftime("%Y-%m-%d", time.gmtime(min_vol_ts / 1000))
        max_vol_date = time.strftime("%Y-%m-%d", time.gmtime(max_vol_ts / 1000))

        low_date = time.strftime("%Y-%m-%d", time.gmtime(low_ts / 1000))
        high_date = time.strftime("%Y-%m-%d", time.gmtime(high_ts / 1000))
        min_close_date = time.strftime("%Y-%m-%d", time.gmtime(all_timestamps[all_closes.index(min_close_price)] / 1000))
        max_close_date = time.strftime("%Y-%m-%d", time.gmtime(all_timestamps[all_closes.index(max_close_price)] / 1000))

        def vs_entry(price):
            return _round_pct((price - float(entry_price)) / float(entry_price) * 100) if entry_price > 0 else 0

        critical_levels = [
            {"price": _round_usdt(low_price), "level": "Low", "vol": int(min(all_volumes)) if all_volumes else None, "vol_usd": _round_usdt(min(all_volumes) * low_price) if all_volumes else None, "date": low_date, "vs_entry": vs_entry(low_price)},
            {"price": _round_usdt(min_close_price), "level": "Min Close", "vol": int(all_volumes[all_closes.index(min_close_price)]) if all_volumes else None, "vol_usd": _round_usdt(all_volumes[all_closes.index(min_close_price)] * min_close_price) if all_volumes else None, "date": min_close_date, "vs_entry": vs_entry(min_close_price)},
            {"price": _round_usdt(current_price), "level": "Current", "vol": int(ohlcv[-1][5]) if ohlcv else None, "vol_usd": _round_usdt(ohlcv[-1][5] * current_price) if ohlcv else None, "date": "today", "vs_entry": vs_entry(current_price)},
            {"price": float(entry_price), "level": "Entry", "vol": None, "vol_usd": None, "date": entry_date, "vs_entry": 0},
            {"price": _round_usdt(max_close_price), "level": "Max Close", "vol": int(all_volumes[all_closes.index(max_close_price)]) if all_volumes else None, "vol_usd": _round_usdt(all_volumes[all_closes.index(max_close_price)] * max_close_price) if all_volumes else None, "date": max_close_date, "vs_entry": vs_entry(max_close_price)},
            {"price": _round_usdt(high_price), "level": "High", "vol": int(max(all_volumes)) if all_volumes else None, "vol_usd": _round_usdt(max(all_volumes) * high_price) if all_volumes else None, "date": high_date, "vs_entry": vs_entry(high_price)},
            {"price": _round_usdt(min_vol_price), "level": "Min Volume", "vol": int(min_vol), "vol_usd": _round_usdt(min_vol * min_vol_price), "date": min_vol_date, "vs_entry": vs_entry(min_vol_price)},
            {"price": _round_usdt(max_vol_price), "level": "Max Volume", "vol": int(max_vol), "vol_usd": _round_usdt(max_vol * max_vol_price), "date": max_vol_date, "vs_entry": vs_entry(max_vol_price)},
        ]

    emoji_upd = {
        "current_price": round(current_price, 6),
        "entry_time": entry_time_calc,
        "pnl_percent": _round_pct(pnl_pct_lev),
        "pnl_usdt": _round_usdt(pnl_usdt_calc),
        "roe_usdt": _round_usdt(roe_usdt),
        "result": "🟢" if pnl_pct_lev > 0 else "🔴",
        "status": "green" if pnl_pct_lev > 0 else "red",
        "last_updated": time.strftime("%Y-%m-%d %H:%M")
    }
    ohlc = {"current": {"high": _round_usdt(max_high), "low": _round_usdt(max_low), "body": _round_usdt(body), "body_pct": body_pct, "upper_wick": _round_usdt(upper_wick), "lower_wick": _round_usdt(lower_wick), "pct": _round_pct(diff_pct), "pct_x": _round_pct(diff_pct * leverage)}, "max": {"price": _round_usdt(max_high), "pct": _round_pct((max_high - entry_price) / entry_price * 100), "pct_x": _round_pct((max_high - entry_price) / entry_price * 100 * leverage), "volatility": _round_usdt(volatility)}, "min": {"price": _round_usdt(max_low), "pct": _round_pct((max_low - entry_price) / entry_price * 100), "pct_x": _round_pct((max_low - entry_price) / entry_price * 100 * leverage), "volatility": _round_usdt(volatility)}}
    if not stats_defined:
        dn = sum(1 for c in ohlcv if c[4] < entry_price)
        dp = sum(1 for c in ohlcv if c[4] > entry_price)
        dn_equal = sum(1 for c in ohlcv if c[4] == entry_price)
        da = len(ohlcv)
        stats = {"dn": dn, "dp": dp, "dn_equal": dn_equal, "da": da}
    summary = {
        "symbol": symbol,
        "entry_price": entry_price,
        "entry_date": entry_date,
        "current_price": _round_usdt(current_price),
        "total_deviation_usdt": _round_usdt(diff_usdt),
        "total_deviation_percent": _round_pct(diff_pct),
        "profitable": current_price > entry_price,
        "max_usdt": _round_usdt(max_usdt),
        "min_usdt": _round_usdt(min_usdt),
        "max_pct": _round_pct(max_pct),
        "min_pct": _round_pct(min_pct),
        "max_usdt_leveraged": _round_usdt(max_usdt_leveraged),
        "min_usdt_leveraged": _round_usdt(min_usdt_leveraged),
        "max_pct_leveraged": _round_pct(max_pct_leveraged),
        "min_pct_leveraged": _round_pct(min_pct_leveraged),
        "max_usdt_with_volume": _round_usdt(max_usdt_with_volume),
        "min_usdt_with_volume": _round_usdt(min_usdt_with_volume),
        "max_usdt_leveraged_volume": _round_usdt(max_usdt_leveraged_volume),
        "min_usdt_leveraged_volume": _round_usdt(min_usdt_leveraged_volume),
        "leverage": leverage,
        "volume": volume,
        "roe_pct": _round_pct(pnl_pct_lev),
        "roe_usdt": _round_usdt(roe_usdt),
        "range_days": range_days,
        "range_pct": _round_pct(range_pct),
        "entry_pct": round(entry_pct, 1),
        "current_pct": round(current_pct, 1),
        "max_high": _round_usdt(max_high),
        "max_low": _round_usdt(max_low),
        "max_high_pct": _round_pct(max_pct),
        "max_low_pct": _round_pct(min_pct)
    }
    try:
        obj = storage.load(obj_id)
        obj.data["emoji_upd"] = emoji_upd
        obj.data["ohlc"] = ohlc
        obj.data["stats"] = stats
        obj.data["chart_updated"] = time.strftime("%Y-%m-%d %H:%M")
        storage.save(obj)
    except Exception:
        pass
    return jsonify({"chart": points, "summary": summary, "emoji_upd": emoji_upd, "ohlc": ohlc, "stats": stats, "critical_levels": critical_levels})
