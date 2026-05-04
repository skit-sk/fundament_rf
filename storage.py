import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from models import FundObj


_storage_instance = None
_metrics_instance = None


def get_storage():
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = JSONStorage()
    return _storage_instance


def get_metrics_storage():
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = MetricsStorage()
    return _metrics_instance


class JSONStorage:
    def __init__(self, data_dir=None):
        if data_dir is None:
            self.data_dir = Path(__file__).parent / 'data'
        else:
            self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.card_dir = self.data_dir / 'card'
        self.card_dir.mkdir(exist_ok=True)

    def _card_folder(self, symbol, obj_id):
        uid5 = obj_id[:8]
        return self.card_dir / f'{symbol}_{uid5}'

    def _card_path(self, symbol, obj_id):
        return self._card_folder(symbol, obj_id) / f'{obj_id}.json'

    def _1d_path(self, symbol, obj_id):
        return self._card_folder(symbol, obj_id) / f'{obj_id}_1D.json'

    def _raw_path(self, symbol, obj_id):
        return self._card_folder(symbol, obj_id) / f'{obj_id}_RAW.json'

    def _ensure_card_folder(self, symbol, obj_id):
        folder = self._card_folder(symbol, obj_id)
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def _path(self, obj_id):
        return self.data_dir / f'{obj_id}.json'

    def save(self, obj: FundObj):
        obj.updated_at = datetime.now()
        with open(self._path(obj.id), 'w', encoding='utf-8') as f:
            json.dump(obj.to_dict(), f, ensure_ascii=False, default=str)
        return obj

    def save_to_card(self, obj: FundObj):
        obj.updated_at = datetime.now()
        symbol = obj.data.get('emoji_entry', {}).get('symbol', 'UNKNOWN')
        self._ensure_card_folder(symbol, obj.id)
        with open(self._card_path(symbol, obj.id), 'w', encoding='utf-8') as f:
            json.dump(obj.to_dict(), f, ensure_ascii=False, default=str)
        return obj

    def load(self, obj_id) -> FundObj:
        p = self._path(obj_id)
        if not p.exists():
            raise FileNotFoundError(f'Object {obj_id} not found')
        with open(p, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return FundObj.from_dict(data)

    def load_from_card(self, symbol, obj_id) -> FundObj:
        p = self._card_path(symbol, obj_id)
        if not p.exists():
            raise FileNotFoundError(f'Object {obj_id} not found in card')
        with open(p, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return FundObj.from_dict(data)

    def list(self):
        objects = []
        for f in self.data_dir.glob('*.json'):
            name = f.name
            if name == 'metrics.json' or name.startswith('card') or name.startswith('1D_') or name.startswith('RAW_'):
                continue
            try:
                with open(f, 'r', encoding='utf-8') as fp:
                    objects.append(FundObj.from_dict(json.load(fp)))
            except (KeyError, json.JSONDecodeError, TypeError):
                continue
        return sorted(objects, key=lambda x: x.created_at, reverse=True)

    def delete(self, obj_id):
        p = self._path(obj_id)
        if not p.exists():
            raise FileNotFoundError(f'Object {obj_id} not found')
        p.unlink()

    def delete_in_card(self, symbol, obj_id):
        p = self._card_path(symbol, obj_id)
        if p.exists():
            p.unlink()
        for suffix in ['_1D.json', '_RAW.json']:
            p = self._card_path(symbol, obj_id).parent / f'{obj_id}{suffix}'
            if p.exists():
                p.unlink()

    def save_1d(self, symbol, obj_id: str, data: dict):
        data['updated_at'] = datetime.now().isoformat()
        self._ensure_card_folder(symbol, obj_id)
        with open(self._1d_path(symbol, obj_id), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, default=str)

    def load_1d(self, symbol, obj_id: str) -> dict:
        p = self._1d_path(symbol, obj_id)
        if not p.exists():
            raise FileNotFoundError(f'1D data for {obj_id} not found')
        with open(p, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save_raw(self, symbol, obj_id: str, data: dict):
        data['updated_at'] = datetime.now().isoformat()
        self._ensure_card_folder(symbol, obj_id)
        with open(self._raw_path(symbol, obj_id), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, default=str)

    def load_raw(self, symbol, obj_id: str) -> dict:
        p = self._raw_path(symbol, obj_id)
        if not p.exists():
            raise FileNotFoundError(f'RAW data for {obj_id} not found')
        with open(p, 'r', encoding='utf-8') as f:
            return json.load(f)

    def delete_1d_raw(self, symbol, obj_id: str):
        for p in [self._1d_path(symbol, obj_id), self._raw_path(symbol, obj_id)]:
            if p.exists():
                p.unlink()

    def exists_1d(self, symbol, obj_id: str) -> bool:
        return self._1d_path(symbol, obj_id).exists()

    def exists_raw(self, symbol, obj_id: str) -> bool:
        return self._raw_path(symbol, obj_id).exists()

    def exists_in_card(self, symbol, obj_id: str) -> bool:
        return self._card_path(symbol, obj_id).exists()

    def get_card_subdirs(self):
        if not self.card_dir.exists():
            return []
        return [d for d in self.card_dir.iterdir() if d.is_dir()]


class MetricsStorage:
    def __init__(self, data_dir=None):
        if data_dir is None:
            self.data_dir = Path(__file__).parent / 'data'
        else:
            self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self._metrics_path = self.data_dir / 'metrics.json'
        self._ensure_metrics()

    def _ensure_metrics(self):
        if not self._metrics_path.exists():
            with open(self._metrics_path, 'w', encoding='utf-8') as f:
                json.dump({'records': [], 'aggregated': {'total_operations': 0, 'avg_api_ms': 0, 'avg_processing_ms': 0, 'avg_writing_ms': 0, 'avg_total_ms': 0, 'failed_count': 0, 'last_operation': None}}, f)

    def load(self) -> dict:
        with open(self._metrics_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save(self, data: dict):
        with open(self._metrics_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, default=str)

    def add_record(self, record: dict):
        data = self.load()
        record['id'] = str(uuid.uuid4())
        data['records'].insert(0, record)
        self._recalculate_aggregated(data)
        self.save(data)

    def _recalculate_aggregated(self, data: dict):
        records = data.get('records', [])
        if not records:
            return
        total = len(records)
        failed = sum(1 for r in records if r.get('result', {}).get('status') == 'failed')
        api_times = [r['duration_ms']['api_request_ms'] for r in records if 'duration_ms' in r and 'api_request_ms' in r['duration_ms']]
        proc_times = [r['duration_ms']['processing_ms'] for r in records if 'duration_ms' in r and 'processing_ms' in r['duration_ms']]
        write_times = [r['duration_ms']['writing_ms'] for r in records if 'duration_ms' in r and 'writing_ms' in r['duration_ms']]
        total_times = [r['duration_ms']['total_ms'] for r in records if 'duration_ms' in r and 'total_ms' in r['duration_ms']]
        data['aggregated'] = {
            'total_operations': total,
            'avg_api_ms': sum(api_times) / len(api_times) if api_times else 0,
            'avg_processing_ms': sum(proc_times) / len(proc_times) if proc_times else 0,
            'avg_writing_ms': sum(write_times) / len(write_times) if write_times else 0,
            'avg_total_ms': sum(total_times) / len(total_times) if total_times else 0,
            'failed_count': failed,
            'last_operation': records[0]['timestamp'] if records else None
        }

    def clear(self):
        self._ensure_metrics()
