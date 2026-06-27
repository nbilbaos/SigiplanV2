import re
import unicodedata


def slugify(value, max_length=80):
    value = unicodedata.normalize('NFKD', value or '')
    value = value.encode('ascii', 'ignore').decode('ascii').lower()
    value = re.sub(r'[^a-z0-9]+', '-', value).strip('-')
    value = re.sub(r'-{2,}', '-', value)
    return value[:max_length].strip('-')
