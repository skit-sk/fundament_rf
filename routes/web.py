from flask import Blueprint, render_template, abort, redirect, url_for
from storage import JSONStorage

bp = Blueprint('web', __name__)
storage = JSONStorage()


@bp.route('/')
def index():
    objects = storage.list()
    return render_template('index.html', objects=objects)


@bp.route('/obj/<obj_id>')
def get_object(obj_id):
    try:
        obj = storage.load(obj_id)
    except FileNotFoundError:
        abort(404)
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