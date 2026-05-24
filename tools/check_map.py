from backend.data.maps_data import MAPS
m = MAPS['world']
print('name:', m['name'])
print('rows:', len(m['rows']), 'cols:', len(m['rows'][0]) if m['rows'] else 0)
# 县域城区
for y in range(12, 18):
    print(f'{y:2d}: {m["rows"][y]}')
print()
# 河流
for y in range(2, 11):
    row = m['rows'][y]
    if '=' in row or '~' in row:
        print(f'{y:2d}: {row}')
# 裂隙/废墟
for y in range(len(m['rows'])):
    row = m['rows'][y]
    if '!' in row or '@' in row:
        print(f'{y:2d}: {row}')