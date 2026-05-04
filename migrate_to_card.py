#!/usr/bin/env python3
import json
import shutil
from pathlib import Path

DATA_DIR = Path(__file__).parent / 'data'
CARD_DIR = DATA_DIR / 'card'


def get_symbol_from_json(obj_id):
    """Load trade JSON and extract symbol"""
    p = DATA_DIR / f'{obj_id}.json'
    if not p.exists():
        return None, None
    try:
        with open(p, 'r') as f:
            data = json.load(f)
        obj_data = data.get('data', {})
        emoji_entry = obj_data.get('emoji_entry', {})
        symbol = emoji_entry.get('symbol', 'UNKNOWN')
        return symbol, data
    except:
        return None, None


def migrate_trade(obj_id):
    symbol, data = get_symbol_from_json(obj_id)
    if not symbol:
        print(f"  [SKIP] {obj_id} - cannot load or no symbol")
        return False

    uid5 = obj_id[:8]
    folder_name = f'{symbol}_{uid5}'
    card_folder = CARD_DIR / folder_name
    card_folder.mkdir(parents=True, exist_ok=True)

    files_moved = []

    trade_file = DATA_DIR / f'{obj_id}.json'
    if trade_file.exists():
        dest = card_folder / f'{obj_id}.json'
        shutil.copy2(trade_file, dest)
        files_moved.append(f'{obj_id}.json')
        print(f"  [MOVE] {trade_file.name} -> {folder_name}/{obj_id}.json")

    d1_file = DATA_DIR / f'1D_{obj_id}.json'
    if d1_file.exists():
        dest = card_folder / f'{obj_id}_1D.json'
        shutil.copy2(d1_file, dest)
        files_moved.append(f'1D_{obj_id}.json -> {obj_id}_1D.json')
        print(f"  [MOVE] 1D_{obj_id}.json -> {folder_name}/{obj_id}_1D.json")

    raw_file = DATA_DIR / f'RAW_{obj_id}.json'
    if raw_file.exists():
        dest = card_folder / f'{obj_id}_RAW.json'
        shutil.copy2(raw_file, dest)
        files_moved.append(f'RAW_{obj_id}.json -> {obj_id}_RAW.json')
        print(f"  [MOVE] RAW_{obj_id}.json -> {folder_name}/{obj_id}_RAW.json")

    if files_moved:
        print(f"  [OK] {obj_id} migrated ({len(files_moved)} files)")
        return True
    else:
        print(f"  [SKIP] {obj_id} - no files to migrate")
        return False


def cleanup_old_files():
    """Delete old 1D_ and RAW_ files after successful migration"""
    files_deleted = 0

    for f in DATA_DIR.glob('1D_*.json'):
        f.unlink()
        files_deleted += 1
        print(f"  [DELETE] {f.name}")

    for f in DATA_DIR.glob('RAW_*.json'):
        f.unlink()
        files_deleted += 1
        print(f"  [DELETE] {f.name}")

    return files_deleted


def main():
    print("=" * 60)
    print("MIGRATION: Old structure -> card/SYMBOL_UID5/ structure")
    print("=" * 60)

    trade_files = [
        f.stem for f in DATA_DIR.glob('*.json')
        if f.name not in ('metrics.json',)
        and not f.name.startswith('card')
        and not f.name.startswith('1D_')
        and not f.name.startswith('RAW_')
    ]

    print(f"\nFound {len(trade_files)} trade files to migrate\n")

    migrated = 0
    for obj_id in trade_files:
        if migrate_trade(obj_id):
            migrated += 1

    print(f"\n{'=' * 60}")
    print(f"Migrated {migrated}/{len(trade_files)} trades")
    print(f"{'=' * 60}")

    confirm = input("\nDelete old files (1D_*.json, RAW_*.json)? (yes/no): ")
    if confirm.lower() == 'yes':
        print("\nDeleting old files...")
        deleted = cleanup_old_files()
        print(f"\nDeleted {deleted} old files")
    else:
        print("\nSkipped deleting old files")

    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE")
    print("=" * 60)
    print(f"\nNew structure:")
    print(f"  {CARD_DIR}/")
    print(f"    SYMBOL_UID5/")
    print(f"      UUID.json       (trade)")
    print(f"      UUID_1D.json    (OHLC days)")
    print(f"      UUID_RAW.json   (RAW candles)")


if __name__ == '__main__':
    main()
