import sys
sys.path.insert(0, '.')
from app.retriever import build_index, load_catalog, search_assessments
print('Building index...')
build_index()
catalog = load_catalog()
print(f'Loaded {len(catalog)} products')

results = search_assessments('Java developer programming', k=5)
print(f'\nJava search: {len(results)} results')
for r in results:
    name = r['name'][:50]
    tt = r['test_type']
    print(f'  {name} [{tt}]')

results2 = search_assessments('personality assessment behavior leadership', k=5)
print(f'\nPersonality search: {len(results2)} results')
for r in results2:
    name = r['name'][:50]
    tt = r['test_type']
    print(f'  {name} [{tt}]')

results3 = search_assessments('numerical reasoning cognitive ability', k=5)
print(f'\nNumerical search: {len(results3)} results')
for r in results3:
    name = r['name'][:50]
    tt = r['test_type']
    print(f'  {name} [{tt}]')
