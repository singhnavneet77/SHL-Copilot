"""
Investigate column meanings with raw data
"""
import requests
from bs4 import BeautifulSoup
import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'}
r = requests.get('https://online.shl.com/gb/en-us/products?orderby=none&page=1&producttypes=1', headers=headers, timeout=30)
soup = BeautifulSoup(r.text, 'html.parser')
table = soup.find('table')
rows = table.find_all('tr')

headers_list = [th.get_text(strip=True) for th in rows[0].find_all(['th','td'])]

# Print all data for known products to understand columns
known_products = ['Occupational Personality Questionnaire', 'Verify', 'Java', 'Python', 'Excel', 'OPQ']

print("Full row data for sample products:")
for row in rows[1:20]:
    cells = row.find_all('td')
    name = cells[1].get_text(strip=True) if len(cells) > 1 else ''
    row_data = {headers_list[i]: cells[i].get_text(strip=True) for i in range(len(headers_list)) if i < len(cells)}
    print(f"\nProduct: {name[:50]}")
    for col, val in row_data.items():
        print(f"  {col}: {val[:80]}")
