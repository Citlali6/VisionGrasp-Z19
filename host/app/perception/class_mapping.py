"""Business IDs, NOT neural class order. Source: installed vendor single file.

See model_sources.json for the exact source hash. model.names determines class IDs.
"""
BUSINESS = {
    'Zip_top_can': ('00', '01'), 'Old_school_bag': ('01', '01'),
    'Newspaper': ('02', '01'), 'Book': ('03', '01'),
    'Toilet_paper': ('04', '02'), 'Peach_pit': ('05', '02'),
    'Cigarette_butts': ('06', '02'), 'Disposable_chopsticks': ('07', '02'),
    'Egg_shell': ('08', '03'), 'Apple_core': ('09', '03'),
    'Watermelon_rind': ('10', '03'), 'Fish_bone': ('11', '03'),
    'Expired_tablets': ('12', '04'), 'Expired_cosmetics': ('13', '04'),
    'Used_batteries': ('14', '04'), 'Syringe': ('15', '04'),
}
# These eight names are explicitly excluded by the deployed garbage_identify.
EXCLUDED = frozenset(('Vegetable_leaf', 'Banana_peel', 'Shell', 'Plastic_bottle',
                      'Basketball', 'Carton', 'Bandage', 'Expired_capsule_drugs'))


def business(label):
    if label in EXCLUDED:
        return None
    if label not in BUSINESS:
        raise ValueError('model label has no audited business mapping: '+str(label))
    item_code, category_code = BUSINESS[label]
    return dict(item_code=item_code, category_code=category_code)
