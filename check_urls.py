import requests
from bs4 import BeautifulSoup
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

headers = {'User-Agent': 'Mozilla/5.0 Windows NT 10.0 Win64 AppleWebKit/537.36'}
r = requests.get('https://online.shl.com/gb/en-us/products?orderby=none&page=1&producttypes=1', headers=headers, timeout=30)
soup = BeautifulSoup(r.text, 'html.parser')

table = soup.find('table')
rows = table.find_all('tr')

print("Checking links in first 5 rows:")
for row in rows[1:6]:
    cells = row.find_all('td')
    name_cell = cells[1] if len(cells) > 1 else cells[0]
    links = row.find_all('a')
    print(f"Row: {name_cell.get_text(strip=True)[:40]}")
    for link in links:
        href = link.get('href', '')
        print(f"  link href: {href}")

# Also check if there are data-* attributes
print("\nChecking for data attributes on rows:")
for row in rows[1:3]:
    for attr in row.attrs:
        print(f"  attr: {attr} = {row[attr]}")
    cells = row.find_all('td')
    for cell in cells[:3]:
        for attr in cell.attrs:
            print(f"  cell attr: {attr} = {cell[attr]}")
