
def normalize_account_name(name: str) -> str:
    name = name.lower()
    name_mappings = {
        'victor': 'viktor'
    }
    return name_mappings.get(name, name)
