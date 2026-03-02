import os
import json
import urllib.request
import re

# Fetch english names so it formats cleanly without accents
url = "https://ddragon.leagueoflegends.com/cdn/14.4.1/data/en_US/champion.json"
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
res = urllib.request.urlopen(req)
data = json.loads(res.read())

champ_dir = r"C:\Users\madan\OneDrive\Desktop\BOT\iconlol\champ"
files = set(os.listdir(champ_dir))

renamed_count = 0
for champ_id, c_data in data['data'].items():
    old_name = f"{champ_id}.webp"
    
    # Get true English name, make it alphanumeric + underscores
    true_name = c_data['name']
    
    # Custom tweaks for edge cases like Nunu & Willump -> Nunu, Renata Glasc -> Renata_Glasc
    clean_name = re.sub(r'[^a-zA-Z0-9]', '_', true_name)
    clean_name = re.sub(r'_+', '_', clean_name).strip('_')
    
    new_name = f"{clean_name}.webp"
    
    old_path = os.path.join(champ_dir, old_name)
    new_path = os.path.join(champ_dir, new_name)
    
    if old_name in files and old_name != new_name:
        if not os.path.exists(new_path): # protect against overwriting
            os.rename(old_path, new_path)
            renamed_count += 1
            print(f"Renamed: {old_name} -> {new_name}")

print(f"Renamed {renamed_count} files successfully!")
