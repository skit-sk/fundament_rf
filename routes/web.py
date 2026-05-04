from flask import Blueprint, render_template, abort, redirect, url_for
from storage import get_storage
import json

bp = Blueprint('web', __name__)
storage = get_storage()


@bp.route('/')
def index():
    objects = storage.list()
    return render_template('index.html', objects=objects)


@bp.route('/obj/<obj_id>')
def get_object(obj_id):
    print(f"[DEBUG] Loading object: {obj_id}")
    try:
        obj = storage.load(obj_id)
    except FileNotFoundError:
        print(f"[DEBUG] Object not found: {obj_id}")
        abort(404)
    print(f"[DEBUG] Rendering card for: {obj.name}")
    return render_template('card.html', obj=obj)


@bp.route('/card/<obj_id>')
def card(obj_id):
    return get_object(obj_id)


@bp.route('/delete/<obj_id>')
def delete_object(obj_id):
    try:
        storage.delete(obj_id)
    except FileNotFoundError:
        pass
    return redirect(url_for('web.index'))


@bp.route('/range_variants_demo')
def range_variants_demo():
    trade_data = None
    days_data = []

    try:
        obj = storage.load('d1b35262-3b28-423a-ab34-f0ab5f719c57')
        symbol = obj.data.get('emoji_entry', {}).get('symbol', 'ETC')
        obj_id = obj.id

        if storage.exists_in_card(symbol, obj_id):
            trade_data = obj.data
            days_data = storage.load_1d(symbol, obj_id).get('days', [])
        elif storage.exists_1d(symbol, obj_id):
            trade_data = obj.data
            days_data = storage.load_1d(symbol, obj_id).get('days', [])
    except (FileNotFoundError, KeyError):
        pass

    return render_template('range_variants_demo.html', trade_data=trade_data, days_data=days_data)