import aiohttp

class DataDragon:
    def __init__(self):
        self.version = None
        self.champions = {}

    async def update_data(self):
        async with aiohttp.ClientSession() as session:
            # 1. Fetch latest version
            version_url = "https://ddragon.leagueoflegends.com/api/versions.json"
            async with session.get(version_url) as resp:
                if resp.status == 200:
                    versions = await resp.json()
                    self.version = versions[0]
            
            if not self.version:
                return

            # 2. Fetch Champion data
            champ_url = f"https://ddragon.leagueoflegends.com/cdn/{self.version}/data/en_US/champion.json"
            async with session.get(champ_url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    champ_data = data.get("data", {})
                    # Map champion ID (string number) to Champion Name and Image key
                    for champ_name, details in champ_data.items():
                        self.champions[details['key']] = {
                            "name": details['name'],
                            "id": details['id'] # Utilisé pour l'URL de l'image
                        }

    def get_champion_info(self, champ_id: int):
        champ_id_str = str(champ_id)
        if champ_id_str in self.champions:
            champ = self.champions[champ_id_str]
            # Retourne le nom et l'URL de la miniature
            icon_url = f"https://ddragon.leagueoflegends.com/cdn/{self.version}/img/champion/{champ['id']}.png"
            return champ['name'], icon_url
        return "Inconnu", None

# Instance globale
ddragon = DataDragon()
