"""
Build final enhanced catalog with proper SHL catalog URLs
"""
import requests
from bs4 import BeautifulSoup
import json
import re
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
}

# The Propositions IDs map to actual SHL test categories shown in their catalog
# Based on catalog research: Propositions refer to assessment use-case categories
PROPOSITION_MAP = {
    '1': 'Screening',
    '2': 'Assessment',
    '3': 'Job-focused',
    '4': 'Talent Development',
    '5': 'Simulations',
    '6': 'Technical Skills',
}

# SHL Test Type from descriptions (keyword-based)
def infer_test_type(name: str, description: str) -> str:
    """Infer test type from name/description"""
    text = (name + ' ' + description).lower()
    name_lower = name.lower()
    
    # Personality & Behavior (check FIRST - these have 'behavior' in knowledge tests too)
    if any(w in text for w in ['personality', 'behaviour', 'motivat', 'opq', 'emotional intelligence']):
        return 'P'
    if 'behavior' in name_lower or 'occupational personality' in name_lower:
        return 'P'
    
    # Simulations (check before K)
    if any(w in name_lower for w in ['simulation', 'inbox', 'in-basket', 'inbasket', 'call center', 'chat sim']):
        return 'S'
    
    # Biodata & Situational Judgment
    if any(w in text for w in ['situational', 'judgment', 'judgement', 'scenario', 'biodata']):
        return 'B'
    
    # Ability & Aptitude (cognitive - check BEFORE K to catch Verify tests)
    verify_patterns = ['verify', 'numerical reasoning', 'verbal reasoning', 'inductive reasoning',
                       'deductive reasoning', 'abstract reasoning', 'numerical ability', 'verbal ability',
                       'cognitive ability', 'cognitive assessment', 'mental agility']
    if any(w in text for w in verify_patterns):
        return 'A'
    if any(w in name_lower for w in ['aptitude', 'reasoning test', 'ability test']):
        return 'A'
    
    # Competencies & Development
    if any(w in text for w in ['360', 'development center', 'assessment center', 'competency framework']):
        return 'D'
    if any(w in text for w in ['competenc', 'leadership competency']):
        return 'C'
    
    # Knowledge & Skills (most programming/technical tests)
    if any(w in text for w in ['java', 'python', 'sql', 'javascript', 'c++', 'php', 'ruby', '.net', 'angular',
                                'react', 'html', 'css', 'linux', 'unix', 'oracle', 'sap', 'excel', 'word',
                                'measures knowledge', 'programming', 'framework', 'fundamentals',
                                'scripting', 'database', 'software', 'coding', 'developer', 'engineer',
                                'technical', 'network', 'web application', 'test measures knowledge']):
        return 'K'
    
    # Default: Knowledge & Skills
    return 'K'


def make_shl_url(name: str) -> str:
    """Construct a valid SHL catalog URL for the product"""
    # Known product URLs from SHL catalog (hardcoded for key products)
    known_urls = {
        'Occupational Personality Questionnaire (OPQ - OPQ32r)': 'https://www.shl.com/solutions/products/product-catalog/view/opq32r/',
        'Motivation Questionnaire (MQ)': 'https://www.shl.com/solutions/products/product-catalog/view/motivation-questionnaire-mq/',
        'Verify - Cognitive Ability': 'https://www.shl.com/solutions/products/product-catalog/view/verify-cognitive-ability/',
        'Verify - Numerical Reasoning': 'https://www.shl.com/solutions/products/product-catalog/view/verify-numerical-reasoning-test/',
        'Verify - Verbal Reasoning': 'https://www.shl.com/solutions/products/product-catalog/view/verify-verbal-reasoning-test/',
        'Verify - Inductive Reasoning': 'https://www.shl.com/solutions/products/product-catalog/view/verify-inductive-reasoning-test/',
        'Verify G+': 'https://www.shl.com/solutions/products/product-catalog/view/verify-g/',
        'Global Skills Assessment': 'https://www.shl.com/solutions/products/product-catalog/view/global-skills-assessment-gsa/',
        'Java 8 (New)': 'https://www.shl.com/solutions/products/product-catalog/view/java-8-new/',
        'Python (New)': 'https://www.shl.com/solutions/products/product-catalog/view/python-new/',
    }
    
    if name in known_urls:
        return known_urls[name]
    
    # Construct URL from name
    slug = name.lower()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'\s+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    slug = slug.strip('-')
    
    return f"https://www.shl.com/solutions/products/product-catalog/view/{slug}/"


print("Building enhanced catalog...")
url = 'https://online.shl.com/gb/en-us/products?orderby=none&page=1&producttypes=1'
r = requests.get(url, headers=headers, timeout=30)
soup = BeautifulSoup(r.text, 'html.parser')
table = soup.find('table')
rows = table.find_all('tr')
headers_list = [th.get_text(strip=True) for th in rows[0].find_all(['th','td'])]

products = []
for row in rows[1:]:
    cells = row.find_all('td')
    if len(cells) < 2:
        continue
    
    row_dict = {}
    for i, h in enumerate(headers_list):
        if i < len(cells):
            row_dict[h] = cells[i].get_text(strip=True)
    
    name = row_dict.get('Name', '').strip()
    if not name or name == 'Name':
        continue
    
    description = row_dict.get('Description', '')[:800]
    
    # Infer test type from content
    test_type = infer_test_type(name, description)
    
    # Map product types based on inferred type
    type_name_map = {
        'A': 'Ability & Aptitude',
        'B': 'Biodata & Situational Judgment',
        'C': 'Competencies',
        'D': 'Development & 360',
        'E': 'Assessment Exercises',
        'K': 'Knowledge & Skills',
        'P': 'Personality & Behavior',
        'S': 'Simulations',
    }
    
    # Parse languages
    lang_raw = row_dict.get('LanguageList', '')
    langs = list(set(lang_raw.split(','))) if lang_raw and lang_raw != 'NULL' else ['en-US']
    lang_codes = list(set([l[:2] for l in langs]))[:8]
    
    # Job levels
    job_levels_raw = row_dict.get('ProductJobLevels', '')
    level_map = {'1': 'Director', '2': 'Entry Level', '3': 'Executive', '4': 'General Population', 
                 '5': 'Graduate', '6': 'Manager', '7': 'Mid-Professional', '8': 'Professional Individual Contributor', '9': 'Supervisor'}
    job_levels = [level_map.get(l, l) for l in job_levels_raw.split(',') if l in level_map]
    
    # Propositions (use case)
    props_raw = row_dict.get('Propositions', '')
    propositions = [PROPOSITION_MAP.get(p, p) for p in props_raw.split(',') if p in PROPOSITION_MAP]
    
    # Build URL
    product_url = make_shl_url(name)
    
    # Add keywords for better search
    keywords = []
    # Extract meaningful words from name and description
    name_words = re.findall(r'\b[A-Za-z][A-Za-z0-9+#.]*\b', name)
    keywords.extend([w for w in name_words if len(w) > 2])
    
    product = {
        'name': name,
        'url': product_url,
        'test_type': test_type,
        'product_types': [type_name_map.get(test_type, 'Knowledge & Skills')],
        'description': description,
        'languages': langs[:10],
        'lang_codes': lang_codes,
        'job_levels': job_levels,
        'propositions': propositions,
        'keywords': keywords,
        'raw_product_types': row_dict.get('ProductTypes', ''),
    }
    products.append(product)

# Show distribution
from collections import Counter
types = Counter(p['test_type'] for p in products)
print(f"Total products: {len(products)}")
print("Test type distribution:")
for t, c in sorted(types.items()):
    type_names = {'A': 'Ability', 'B': 'Biodata/SJT', 'C': 'Competencies', 'K': 'Knowledge/Skills', 'P': 'Personality', 'S': 'Simulations', 'D': 'Development', 'E': 'Exercises'}
    print(f"  {t} ({type_names.get(t,'?')}): {c}")

# Sample
print("\nSample products by type:")
for test_type in ['K', 'P', 'A', 'B']:
    sample = [p for p in products if p['test_type'] == test_type][:2]
    for p in sample:
        print(f"  [{p['test_type']}] {p['name'][:50]} -> {p['url'][:60]}")

with open('data/catalog.json', 'w', encoding='utf-8') as f:
    json.dump(products, f, indent=2, ensure_ascii=False)
print(f"\nSaved {len(products)} products to data/catalog.json")
