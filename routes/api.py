import re
from flask import Blueprint, request, jsonify, redirect, url_for
from models import FundObj
from storage import JSONStorage

bp = Blueprint('api', __name__, url_prefix='/api')
storage = JSONStorage()


def parse_emoji_data(text: str) -> dict:
    data = {}
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)

    m = re.search(r'🏗️ (\d+)', text)
    if m: data['number'] = int(m.group(1))

    m = re.search(r'🚏(\w+)', text)
    if m: data['symbol'] = m.group(1)

    m = re.search(r'🧾([\d.]+)', text)
    if m: data['entry_price'] = float(m.group(1))

    m = re.search(r'📆(\d{4}-\d{2}-\d{2})', text)
    if m: data['entry_date'] = m.group(1)

    m = re.search(r'🕒 ?(\d+)', text)
    if m: data['entry_time'] = int(m.group(1))

    m = re.search(r'🧱\s*([\d.]+)', text)
    if m: data['volume'] = float(m.group(1))

    m = re.search(r'🫧\s*([-\d.]+)', text)
    if m: data['pnl_percent'] = float(m.group(1))

    m = re.search(r'[📈📉]\s*([-\d.]+)', text)
    if m: data['pnl_usdt'] = float(m.group(1))

    m = re.search(r'📦 ([🟢🔴])', text)
    if m:
        data['result'] = m.group(1)
        data['status'] = 'green' if m.group(1) == '🟢' else 'red'

    result = {
        'emoji_entry': data,
        'leverage': 10,
        'emoji_upd': {},
        'ohlc': {},
        'stats': {}
    }
    return result


@bp.route('/objects', methods=['GET'])
def list_objects():
    objects = storage.list()
    return jsonify([obj.to_dict() for obj in objects])


@bp.route('/objects', methods=['POST'])
def create_object():
    data = request.json
    obj = FundObj(
        obj_type=data.get('obj_type', ''),
        name=data.get('name', ''),
        data=data.get('data', {})
    )
    storage.save(obj)
    return jsonify(obj.to_dict()), 201


@bp.route('/objects/from-emoji', methods=['POST'])
def create_from_emoji():
    raw = request.form.get('emoji_data', '')
    lines = [l.strip() for l in raw.strip().split('\n') if l.strip()]

    for line in lines:
        data = parse_emoji_data(line)
        if 'number' in data and 'symbol' in data:
            name = f"{data['symbol']} #{data['number']}"
        elif 'symbol' in data:
            name = data['symbol']
        else:
            name = "New Card"

        obj = FundObj(obj_type='сделка', name=name, data=data)
        storage.save(obj)

    return redirect(url_for('web.index'))


@bp.route('/objects/<obj_id>', methods=['DELETE'])
def delete_object(obj_id):
    try:
        storage.delete(obj_id)
        return jsonify({'ok': True})
    except FileNotFoundError:
        return jsonify({'error': 'Not found'}), 404