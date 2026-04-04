import argparse
import json
from typing import Dict, List

from app import sync_player_bios_from_nba_profiles


def _summary_lines(result: Dict) -> List[str]:
    return [
        'Player bios backfill finished.',
        f"Players seen: {int(result.get('players_seen') or 0)}",
        f"Players updated: {int(result.get('players_bio_updated') or 0)}",
        f"Fields filled: {int(result.get('fields_filled') or 0)}",
        f"Missing birth dates left: {int(result.get('players_missing_birth_date') or 0)}",
        f"Missing heights left: {int(result.get('players_missing_height') or 0)}",
        f"Missing weights left: {int(result.get('players_missing_weight') or 0)}",
    ]



def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description='One-time player bio backfill from official NBA.com player profile pages.'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Print the final result as JSON instead of friendly text.'
    )
    args = parser.parse_args(argv)

    try:
        result = sync_player_bios_from_nba_profiles()
    except Exception as exc:
        if args.json:
            print(json.dumps({'ok': False, 'error': str(exc)}))
        else:
            print(f'Player bios backfill failed: {exc}')
        return 1

    if args.json:
        print(json.dumps({'ok': True, **result}, indent=2))
    else:
        for line in _summary_lines(result):
            print(line)
        errors = result.get('errors') or []
        if errors:
            print('\nNotes:')
            for item in errors[:10]:
                print(f'- {item}')
            remaining = len(errors) - min(len(errors), 10)
            if remaining > 0:
                print(f'- ... and {remaining} more')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
