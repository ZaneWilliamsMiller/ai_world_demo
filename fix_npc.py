import re
path = 'C:/Users/AAWZV/.qclaw/workspace/living-paper/backend/data/npcs_data.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()
# Fix wander_maps_whitelist - they're tuples with map names
old_maps = ['county', 'wild', 'dock', 'village', 'post', 'academy', 'temple', 'guild', 'checkpoint', 'mill']
for m in old_maps:
    content = content.replace(f'("{m}",', '("world",')
    content = content.replace(f'"{m}"', '"world"')
with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Done')