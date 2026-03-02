with open("bot.py", "r", encoding="utf-8") as f:
    content = f.read()

bad_func = """def get_champ_emoji(champ_name, default="❔"):
    safe_name = champ_name.replace(" & ", "_").replace(" ", "_").replace("'", "_").replace(".", "")
    return get_champ_emoji(safe_name, get_champ_emoji(champ_name, default))"""

good_func = """def get_champ_emoji(champ_name, default="❔"):
    safe_name = champ_name.replace(" & ", "_").replace(" ", "_").replace("'", "_").replace(".", "")
    return CHAMP_EMOJIS.get(safe_name, CHAMP_EMOJIS.get(champ_name, default))"""

content = content.replace(bad_func, good_func)

with open("bot.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Fixed recursion.")
