import aiohttp
import os
from dotenv import load_dotenv
import logging

load_dotenv()

logger = logging.getLogger("RiotAPI")

# L'API Accounts est globale (americas, asia, europe, esports)
# Riot recommande d'utiliser le cluster au plus proche ou europe pour EUW. 
RIOT_ACCOUNT_URL = "https://europe.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"

async def get_riot_account(game_name: str, tag_line: str):
    RIOT_API_KEY = os.getenv('RIOT_API_KEY')
    if not RIOT_API_KEY or RIOT_API_KEY == 'votre_api_key_ici':
        raise ValueError("La clé d'API Riot n'est pas configurée.")
        
    url = RIOT_ACCOUNT_URL.format(game_name=game_name, tag_line=tag_line)
    headers = {
        "X-Riot-Token": RIOT_API_KEY
    }
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data # Contient puuid, gameName, tagLine
                elif response.status == 404:
                    logger.warning(f"[API] Joueur non trouvé: {game_name}#{tag_line} (404)")
                    return None # Joueur non trouvé
                elif response.status == 403:
                    logger.error("[API] Clé d'API Riot invalide ou expirée (403).")
                    raise Exception("Clé d'API invalide ou expirée.")
                else:
                    error_text = await response.text()
                    logger.error(f"[API] Erreur {response.status} lors de la requête compte: {error_text}")
                    raise Exception(f"Erreur API Riot : {response.status}")
        except aiohttp.ClientError as e:
            logger.exception(f"[API] Erreur réseau lors de la requête compte: {e}")
            raise

async def get_summoner_by_puuid(puuid: str, region: str = "euw1"):
    RIOT_API_KEY = os.getenv('RIOT_API_KEY')
    url = f"https://{region}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 403:
                    logger.error("[API] Clé d'API Riot invalide ou expirée (403) [get_summoner].")
                else:
                    logger.warning(f"[API] Erreur {response.status} pour get_summoner_by_puuid ({puuid})")
                return None
        except aiohttp.ClientError as e:
            logger.error(f"[API] Erreur réseau get_summoner_by_puuid: {e}")
            return None

async def get_league_entries(puuid: str, region: str = "euw1"):
    RIOT_API_KEY = os.getenv('RIOT_API_KEY')
    url = f"https://{region}.api.riotgames.com/lol/league/v4/entries/by-puuid/{puuid}"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 403:
                    logger.error("[API] Clé d'API Riot invalide ou expirée (403) [get_league_entries].")
                else:
                    logger.warning(f"[API] Erreur {response.status} pour get_league_entries ({puuid})")
                return []
        except aiohttp.ClientError as e:
            logger.error(f"[API] Erreur réseau get_league_entries: {e}")
            return []

async def get_active_game(puuid: str, region: str = "euw1"):
    RIOT_API_KEY = os.getenv('RIOT_API_KEY')
    url = f"https://{region}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{puuid}"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 404:
                    return None # Non en partie
                elif response.status == 403:
                    logger.error("[API] Clé d'API Riot invalide ou expirée (403) [get_active_game].")
                else:
                    logger.warning(f"[API] Erreur {response.status} pour get_active_game ({puuid})")
                return None
        except aiohttp.ClientError as e:
            logger.error(f"[API] Erreur réseau get_active_game: {e}")
            return None

async def get_latest_match_id(puuid: str, region: str = "europe"):
    RIOT_API_KEY = os.getenv('RIOT_API_KEY')
    url = f"https://{region}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count=1"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data[0] if data else None
                elif response.status == 403:
                    logger.error("[API] Clé d'API Riot invalide ou expirée (403) [get_latest_match_id].")
                else:
                    logger.warning(f"[API] Erreur {response.status} pour get_latest_match_id ({puuid})")
                return None
        except aiohttp.ClientError as e:
            logger.error(f"[API] Erreur réseau get_latest_match_id: {e}")
            return None

async def get_match_details(match_id: str, region: str = "europe"):
    RIOT_API_KEY = os.getenv('RIOT_API_KEY')
    url = f"https://{region}.api.riotgames.com/lol/match/v5/matches/{match_id}"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 403:
                    logger.error("[API] Clé d'API Riot invalide ou expirée (403) [get_match_details].")
                else:
                    logger.warning(f"[API] Erreur {response.status} pour get_match_details ({match_id})")
                return None
        except aiohttp.ClientError as e:
            logger.error(f"[API] Erreur réseau get_match_details: {e}")
            return None

async def get_top_champion_masteries(puuid: str, count: int = 3, region: str = "euw1"):
    RIOT_API_KEY = os.getenv('RIOT_API_KEY')
    url = f"https://{region}.api.riotgames.com/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}/top?count={count}"
    headers = {"X-Riot-Token": RIOT_API_KEY}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 403:
                    logger.error("[API] Clé d'API Riot invalide ou expirée (403) [get_top_champion_masteries].")
                else:
                    logger.warning(f"[API] Erreur {response.status} pour get_top_champion_masteries ({puuid})")
                return []
        except aiohttp.ClientError as e:
            logger.error(f"[API] Erreur réseau get_top_champion_masteries: {e}")
            return []
