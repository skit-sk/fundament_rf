import re
from flask import Blueprint, request, jsonify, redirect, url_for
from models import FundObj
from storage import get_storage

bp = Blueprint('api', __name__, url_prefix='/api')
storage = get_storage()


def parse_emoji_data(text: str) -> dict:
    data = {}
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)

    m = re.search(r'🏗️\s*(\d+)', text)
    if m: data['number'] = int(m.group(1))

    m = re.search(r'🚏\s*(\w+)', text)
    if m: data['symbol'] = m.group(1).upper()

    m = re.search(r'🧾\s*([\d.]+)', text)
    if m: 
        # Сохраняем точное значение как float (без принудительного округления)
        data['entry_price'] = float(m.group(1))

    m = re.search(r'📆\s*(\d{4}-\d{2}-\d{2})', text)
    if m: data['entry_date'] = m.group(1)

    m = re.search(r'🕒\s*(\d+)', text)
    if m: data['entry_time'] = int(m.group(1))

    m = re.search(r'🧱\s*([\d.]+)', text)
    if m: data['volume'] = float(m.group(1))

    m = re.search(r'🫧\s*([-\d.]+)', text)
    if m: data['pnl_percent'] = float(m.group(1))

    m = re.search(r'[📈📉]\s*([-\d.]+)', text)
    if m: data['pnl_usdt'] = float(m.group(1))

    m = re.search(r'📦\s*([🟢🔴])', text)
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
    storage.save_to_card(obj)
    return jsonify(obj.to_dict()), 201


@bp.route('/objects/from-emoji', methods=['POST'])
def create_from_emoji():
    raw = request.form.get('emoji_data', '')
    cleaned = re.sub(r'\s+', ' ', raw).strip()
    blocks = re.split(r'(?=🏗️)', cleaned)
    
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        data = parse_emoji_data(block)
        emoji = data.get('emoji_entry', {})
        
        if 'number' in emoji and 'symbol' in emoji:
            name = f"{emoji['symbol']} #{emoji['number']}"
        elif 'symbol' in emoji:
            name = emoji['symbol']
        else:
            name = "New Card"

        obj = FundObj(obj_type='сделка', name=name, data=data)
        storage.save(obj)
        storage.save_to_card(obj)

    return redirect(url_for('web.index'))


@bp.route('/objects/<obj_id>', methods=['DELETE'])
def delete_object(obj_id):
    try:
        storage.delete(obj_id)
        return jsonify({'ok': True})
    except FileNotFoundError:
        return jsonify({'error': 'Not found'}), 404
