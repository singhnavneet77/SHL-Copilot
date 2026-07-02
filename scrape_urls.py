"""
Scrape SHL catalog URLs from shl.com/solutions/products/product-catalog/
"""
import requests
from bs4 import BeautifulSoup
import json, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,*/*',
}

all_products = {}

for start in range(0, 500, 12):
    url = f'https://www.shl.com/solutions/products/product-catalog/?start={start}&type=1'
    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Find product links in the catalog
        all_links = soup.find_all('a', href=True)
        
        found_any = False
        for link in all_links:
            href = link.get('href', '')
            text = link.get_text(strip=True)
            
            # Filter for product catalog links
            if ('/solutions/products/' in href and 
                'product-catalog' not in href and 
                text and len(text) > 3):
                full_url = f"https://www.shl.com{href}" if href.startswith('/') else href
                all_products[text] = full_url
                found_any = True
        
        if found_any:
            print(f"start={start}: Found products, total now: {len(all_products)}")
        else:
            print(f"start={start}: No new products found, stopping")
            if start > 0:
                break
        
        time.sleep(0.5)
    except Exception as e:
        print(f"Error at start={start}: {e}")
        break

print(f"\nTotal unique products: {len(all_products)}")
for name, url in list(all_products.items())[:10]:
    print(f"  {name} -> {url}")

# Save
with open('data/catalog_urls.json', 'w', encoding='utf-8') as f:
    json.dump(all_products, f, indent=2, ensure_ascii=False)
print("Saved to data/catalog_urls.json")
