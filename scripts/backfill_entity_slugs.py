"""Genera slugs para entidades existentes que aun no tienen uno.

Uso:
  FLASK_ENV=prod python scripts/backfill_entity_slugs.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models.entity import Entity


def main():
    app = create_app(os.environ.get('FLASK_ENV', 'dev'))
    with app.app_context():
        updated = 0
        for entity in Entity.objects:
            if entity.slug:
                continue
            entity.slug = ''
            entity.save()
            updated += 1
            print(f'{entity.id} {entity.slug}')
        print(f'Entidades actualizadas: {updated}')


if __name__ == '__main__':
    main()
