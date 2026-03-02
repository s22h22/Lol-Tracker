import re

with open("bot.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add get_champ_emoji function
if "def get_champ_emoji(" not in content:
    replacement = '''from emojis import CHAMP_EMOJIS

def get_champ_emoji(champ_name, default="❔"):
    safe_name = champ_name.replace(" & ", "_").replace(" ", "_").replace("'", "_").replace(".", "")
    return CHAMP_EMOJIS.get(safe_name, CHAMP_EMOJIS.get(champ_name, default))
'''
    content = content.replace('from emojis import CHAMP_EMOJIS', replacement)

# 2. Replace CHAMP_EMOJIS.get with get_champ_emoji
content = content.replace('CHAMP_EMOJIS.get(', 'get_champ_emoji(')

with open("bot.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Replaced successfully!")
