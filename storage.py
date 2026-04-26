import json
import os
from datetime import datetime
from pathlib import Path
from models import FundObj


class JSONStorage:
    def __init__(self, data_dir=None):
        if data_dir is None:
            self.data_dir = Path(__file__).parent / 'data'
        else:
            self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

    def _path(self, obj_id):
        return self.data_dir / f'{obj_id}.json'

    def save(self, obj: FundObj):
        obj.updated_at = datetime.now()
        with open(self._path(obj.id), 'w', encoding='utf-8') as f:
            json.dump(obj.to_dict(), f, ensure_ascii=False, default=str)
        return obj

    def load(self, obj_id) -> FundObj:
        p = self._path(obj_id)
        if not p.exists():
            for f in self.data_dir.glob('*.json'):
                with open(f, 'r', encoding='utf-8') as fp:
                    data = json.load(fp)
                    if data.get('id') == obj_id:
                        return FundObj.from_dict(data)
            raise FileNotFoundError(f'Object {obj_id} not found')
        with open(p, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return FundObj.from_dict(data)

    def list(self):
        objects = []
        for f in self.data_dir.glob('*.json'):
            with open(f, 'r', encoding='utf-8') as fp:
                objects.append(FundObj.from_dict(json.load(fp)))
        return sorted(objects, key=lambda x: x.created_at, reverse=True)

    def delete(self, obj_id):
        p = self._path(obj_id)
        if not p.exists():
            for f in self.data_dir.glob('*.json'):
                with open(f, 'r', encoding='utf-8') as fp:
                    data = json.load(fp)
                    if data.get('id') == obj_id:
                        f.unlink()
                        return
            raise FileNotFoundError(f'Object {obj_id} not found')
        p.unlink()