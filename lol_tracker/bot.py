import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
from dotenv import load_dotenv
from datetime import datetime
import logging
import asyncio
from logging.handlers import RotatingFileHandler

# Configuration du module de logging
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')

log_fileHandler = RotatingFileHandler(
    "bot.log", maxBytes=5 * 1024 * 1024, backupCount=2, encoding='utf-8'
)
log_fileHandler.setFormatter(log_formatter)

log_consoleHandler = logging.StreamHandler()
log_consoleHandler.setFormatter(log_formatter)

logger = logging.getLogger("TrackerBot")
logger.setLevel(logging.INFO)
logger.addHandler(log_fileHandler)
logger.addHandler(log_consoleHandler)

from database import init_db, link_account, get_account, get_all_accounts, get_all_tracked_users, update_user_match, get_guild_tracking_channel, set_guild_tracking_channel, unlink_account, update_user_active_match
from riot_api import get_riot_account, get_summoner_by_puuid, get_league_entries, get_active_game, get_latest_match_id, get_match_details, get_top_champion_masteries
from data_dragon import ddragon
from emojis import CHAMP_EMOJIS

def get_champ_emoji(champ_name, default="❔"):
    safe_name = champ_name.replace(" & ", "_").replace(" ", "_").replace("'", "_").replace(".", "")
    return CHAMP_EMOJIS.get(safe_name, CHAMP_EMOJIS.get(champ_name, default))


# Map des icônes de rang (Vous pourrez remplacer ces emojis par des emojis personnalisés : <:name:id>)
RANK_EMOJIS = {
    "Iron": "<:Season_2023__Iron:1475000639565074533>",
    "Bronze": "<:Season_2023__Bronze:1475000669344759838>",
    "Silver": "<:Season_2023__Silver:1475000678026838126>",
    "Gold": "<:Season_2023__Gold:1475000675149676635>",
    "Platinum": "<:Season_2023__Platinum:1475000731408007248>",
    "Emerald": "<:Season_2023__Emerald:1475000673677344829>",
    "Diamond": "<:Season_2023__Diamond:1475000672054280274>",
    "Master": "<:Season_2023__Master:1475000730170556560>",
    "Grandmaster": "<:Season_2023__Grandmaster:1475000676391194788>",
    "Challenger": "<:Season_2023__Challenger:1475000670686806046>"
}


async def build_live_embed(game_data, target_puuid, target_game_name):
    participants = game_data['participants']
    
    async def fetch_rank(p):
        if 'puuid' not in p: return "Unranked"
        try:
            entries = await get_league_entries(p['puuid'])
            if not entries: return "Unranked"
            solo = next((q for q in entries if q['queueType'] == "RANKED_SOLO_5x5"), None)
            flex = next((q for q in entries if q['queueType'] == "RANKED_FLEX_SR"), None)
            best = solo or flex
            if best:
                tier = best['tier'].upper()
                rank = best['rank']
                return f"{tier}  {rank}"
            return "Unranked"
        except:
            return "Unranked"

    ranks = await asyncio.gather(*(fetch_rank(p) for p in participants))
    
    blue_team = []
    red_team = []
    
    for i, p in enumerate(participants):
        champ_id = p['championId']
        champ_name, _ = ddragon.get_champion_info(champ_id)
        c_emoji = get_champ_emoji(champ_name, "❔")
        
        p_name = p.get('riotIdGameName') or p.get('summonerName', 'Inconnu')
        rank_str = ranks[i]
        
        display_name = p_name
        if p.get('puuid') == target_puuid:
            display_name = f"__**{p_name}**__"
            
        line = f"• {c_emoji} | {display_name} | `{rank_str}`\n───────────────"
        
        if p['teamId'] == 100:
            blue_team.append(line)
        else:
            red_team.append(line)

    game_mode = game_data.get('gameMode', 'Inconnu')
    game_length = game_data.get('gameLength', 0)
    minutes = game_length // 60
    
    embed = discord.Embed(color=0x2b2d31)
    
    red_circle_url = "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/1f534.png"
    hourglass_url = "https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/23f3.png"
    
    embed.set_author(name=f"{target_game_name} | Actuellement en partie | {game_mode}", icon_url=red_circle_url)
    embed.add_field(name="Équipe Blue :", value="\n".join(blue_team) if blue_team else "Vide", inline=True)
    embed.add_field(name="Équipe Red :", value="\n".join(red_team) if red_team else "Vide", inline=True)
    
    footer_text = f" En game depuis : {minutes} minutes" if minutes > 0 else " La partie vient de commencer"
    embed.set_footer(text=footer_text, icon_url=hourglass_url)
    
    return embed

# Chargement des variables d'environnement
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Configuration du Bot
class TrackerBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!", 
            intents=discord.Intents.default()
        )
    
    async def setup_hook(self):
        # Initialisation de la base de données
        await init_db()
        logger.info("Base de données initialisée.")
        # Téléchargement des données DataDragon (Champions)
        await ddragon.update_data()
        logger.info("Données DataDragon (Champions) chargées.")
        
        # Démarrage de la boucle d'analyse des parties
        check_matches.start()
        logger.info("Tracer de partie (Match Tracking) lancé.")
        
        hourly_recap.start()
        logger.info("Récapitulatif horaire des LP lancé.")
        
        # Synchronisation des commandes Slash avec Discord
        await self.tree.sync()
        logger.info("Commandes Slash synchronisées avec succès.")

bot = TrackerBot()

@bot.event
async def on_ready():
    logger.info(f'Connecté en tant que {bot.user} (ID: {bot.user.id})')
    logger.info('------')

@bot.tree.command(name="link", description="Lier un compte Riot Games à un compte Discord.")
@app_commands.describe(
    pseudo="Le Pseudo Riot (Exemple : Faker)",
    tag="Le Tag Riot sans le # (Exemple : KR ou EUW)",
    utilisateur="Le joueur Discord à lier (Laissez vide pour vous-même)"
)
async def link(interaction: discord.Interaction, pseudo: str, tag: str, utilisateur: discord.Member = None):
    # Sécurité : vérifier si on veut lier le compte de quelqu'un d'autre
    if utilisateur and utilisateur.id != interaction.user.id:
        if not interaction.permissions.administrator:
            await interaction.response.send_message("❌ Vous devez être administrateur pour lier le compte d'un autre joueur.", ephemeral=True)
            return

    await interaction.response.defer(ephemeral=True) # Indique que le bot traite la demande (message privé)
    
    # Nettoyage au cas où l'utilisateur mettrait un # dans le tag
    tag = tag.replace("#", "")
    target_user = utilisateur or interaction.user
    
    try:
        account_data = await get_riot_account(pseudo, tag)
        
        if account_data:
            # Récupération du PUUID et enregistrement
            puuid = account_data['puuid']
            actual_game_name = account_data['gameName']
            actual_tag_line = account_data['tagLine']
            
            await link_account(
                discord_id=target_user.id,
                puuid=puuid,
                game_name=actual_game_name,
                tag_line=actual_tag_line
            )
            
            if utilisateur:
                await interaction.followup.send(f"✅ Compte lié avec succès ! {target_user.mention} est désormais reconnu comme **{actual_game_name}#{actual_tag_line}**.")
            else:
                await interaction.followup.send(f"✅ Compte lié avec succès ! Vous êtes désormais reconnu comme **{actual_game_name}#{actual_tag_line}**.")
        else:
            await interaction.followup.send(f"❌ Impossible de trouver le compte `{pseudo}#{tag}`. Vérifiez l'orthographe.")
            
    except Exception as e:
        logger.exception(f"Erreur lors de la commande /link pour {pseudo}#{tag} par l'utilisateur {interaction.user.id}")
        await interaction.followup.send(f"⚠️ Une erreur inattendue s'est produite lors de la liaison de compte. L'administrateur peut consulter les logs pour plus de détails.")

@bot.tree.command(name="unlink", description="Délier votre compte Riot Games actuel ou celui d'un utilisateur (Admin).")
@app_commands.describe(utilisateur="Le joueur Discord à délier (Admin uniquement, laissez vide pour vous-même)")
async def unlink(interaction: discord.Interaction, utilisateur: discord.Member = None):
    # Si on essaie de délier quelqu'un d'autre, il faut être admin
    if utilisateur and utilisateur.id != interaction.user.id:
        if not interaction.permissions.administrator:
            await interaction.response.send_message("❌ Vous devez être administrateur pour délier le compte d'un autre joueur.", ephemeral=True)
            return
            
    target_user = utilisateur or interaction.user
    account = await get_account(target_user.id)
    
    if account:
        await unlink_account(target_user.id)
        if utilisateur:
            await interaction.response.send_message(f"✅ Le compte de {target_user.mention} a été délié avec succès.", ephemeral=True)
        else:
            await interaction.response.send_message("✅ Votre compte a été délié avec succès.", ephemeral=True)
    else:
        if utilisateur:
            await interaction.response.send_message(f"❌ {target_user.mention} n'a pas de compte lié.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Vous n'avez aucun compte lié actuellement.", ephemeral=True)

@bot.tree.command(name="profile", description="Affiche le compte Riot lié à votre compte Discord.")
async def profile(interaction: discord.Interaction):
    account = await get_account(interaction.user.id)
    
    if account:
        puuid, game_name, tag_line = account
        await interaction.response.send_message(f"Votre compte Discord est actuellement lié à **{game_name}#{tag_line}**.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Vous n'avez pas de compte lié. Utilisez la commande `/link`.", ephemeral=True)

@bot.tree.command(name="stats", description="Affiche les statistiques (rang, niveau) d'un joueur.")
@app_commands.describe(utilisateur="Le joueur Discord dont vous voulez voir les stats (laissez vide pour vous-même)")
async def stats(interaction: discord.Interaction, utilisateur: discord.Member = None):
    await interaction.response.defer(ephemeral=False)
    
    target_user = utilisateur or interaction.user
    account = await get_account(target_user.id)
    
    if not account:
        if utilisateur:
            await interaction.followup.send(f"❌ {target_user.mention} n'a pas encore lié de compte Riot.")
        else:
            await interaction.followup.send("❌ Vous n'avez pas lié de compte Riot. Utilisez d'abord la commande `/link`.")
        return
        
    puuid, game_name, tag_line = account
    
    try:
        # 1. Obtenir les infos du Summoner (niveau, id classé)
        summoner_data = await get_summoner_by_puuid(puuid)
        
        # Riot ne renvoie plus d'id mais toujours le niveau et l'icône, donc on vérifie la présence de 'summonerLevel'
        if not summoner_data or 'summonerLevel' not in summoner_data:
            await interaction.followup.send("❌ Impossible de récupérer les données de ce joueur. S'est-il déjà connecté à League of Legends sur la région par défaut (EUW) ?")
            return
            
        summoner_level = summoner_data['summonerLevel']
        profile_icon_id = summoner_data['profileIconId']
        
        # 2. Obtenir les rangs
        league_data = await get_league_entries(puuid)
        
        # 3. Préparer l'Embed Discord
        embed = discord.Embed(
            title=f"Statistiques de {game_name}#{tag_line}",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=f"https://ddragon.leagueoflegends.com/cdn/14.4.1/img/profileicon/{profile_icon_id}.png")
        embed.add_field(name="Niveau", value=str(summoner_level), inline=False)
        
        if not league_data:
            embed.add_field(name="Classé Solo/Duo", value="Unranked", inline=True)
            embed.add_field(name="Classé Flex", value="Unranked", inline=True)
        else:
            solo_data = next((q for q in league_data if q['queueType'] == "RANKED_SOLO_5x5"), None)
            flex_data = next((q for q in league_data if q['queueType'] == "RANKED_FLEX_SR"), None)

            def add_queue_field(queue_info, name):
                if queue_info:
                    tier = queue_info['tier'].capitalize()
                    rank = queue_info['rank']
                    lp = queue_info['leaguePoints']
                    wins = queue_info['wins']
                    losses = queue_info['losses']
                    total_games = wins + losses
                    winrate = int((wins / total_games) * 100) if total_games > 0 else 0
                    
                    emoji = RANK_EMOJIS.get(tier, "")
                    embed.add_field(
                        name=name, 
                        value=f"{emoji} **{tier} {rank}** ({lp} LP)\n{wins}W / {losses}L (WR: {winrate}%)", 
                        inline=True
                    )
                else:
                    embed.add_field(name=name, value="Unranked", inline=True)

            add_queue_field(solo_data, "Classé Solo/Duo")
            add_queue_field(flex_data, "Classé Flex")
            
        # 4. Top 5 Champions (Mastery)
        top_masteries = await get_top_champion_masteries(puuid, count=5)
        if top_masteries:
            mastery_lines = []
            for m in top_masteries:
                champ_id = m['championId']
                champ_level = m['championLevel']
                champ_points = m['championPoints']
                
                # Format points (e.g., 1500000 -> 1.5M, 50000 -> 50K)
                if champ_points >= 1000000:
                    pts_str = f"{champ_points / 1000000:.1f}M"
                elif champ_points >= 1000:
                    pts_str = f"{champ_points / 1000:.1f}K"
                else:
                    pts_str = str(champ_points)
                    
                champ_name, _ = ddragon.get_champion_info(champ_id)
                c_emoji = get_champ_emoji(champ_name, "")
                
                mastery_lines.append(f"• {c_emoji} **{champ_name}** - Lvl {champ_level} ({pts_str} pts)")
                
            embed.add_field(name="Top 5 Champions", value="\n".join(mastery_lines), inline=False)
            
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        logger.exception(f"Erreur lors de la récupération des stats pour le PUUID {puuid} ({game_name}#{tag_line})")
        await interaction.followup.send("⚠️ Impossible de récupérer les statistiques pour le moment (Erreur API ou compte non trouvé).")

@bot.tree.command(name="users", description="(Admin uniquement) Affiche tous les comptes liés de ce serveur.")
@app_commands.default_permissions(administrator=True)
async def list_users(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    accounts = await get_all_accounts()
    
    if not accounts:
        await interaction.followup.send("Aucun compte n'a encore été lié à ce bot.")
        return
        
    # Filtrer les membres uniquement pour le serveur (guilde) actuel
    guild = interaction.guild
    if not guild:
        await interaction.followup.send("❌ Cette commande ne peut être utilisée que dans un serveur.")
        return
        
    embed = discord.Embed(
        title=f"Comptes liés sur {guild.name}",
        color=discord.Color.red()
    )
    
    count = 0
    for discord_id, game_name, tag_line in accounts:
        try:
            # fetch_member garantit qu'on trouve l'utilisateur même s'il n'est pas en cache
            member = await guild.fetch_member(discord_id)
            count += 1
            embed.add_field(name=member.display_name, value=f"{game_name}#{tag_line}", inline=False)
        except discord.NotFound:
            # L'utilisateur a quitté le serveur
            pass
            
    if count == 0:
        await interaction.followup.send("Aucun membre de ce serveur n'a lié son compte Riot.")
        return
        
    embed.description = f"Total: {count} compte(s) sur ce serveur"
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="live", description="Affiche la partie en cours d'un joueur.")
@app_commands.describe(utilisateur="Le joueur Discord dont vous voulez voir la partie (laissez vide pour vous-même)")
async def live(interaction: discord.Interaction, utilisateur: discord.Member = None):
    await interaction.response.defer(ephemeral=False)
    
    target_user = utilisateur or interaction.user
    account = await get_account(target_user.id)
    
    if not account:
        if utilisateur:
            await interaction.followup.send(f"❌ {target_user.mention} n'a pas encore lié de compte Riot.")
        else:
            await interaction.followup.send("❌ Vous n'avez pas lié de compte Riot. Utilisez d'abord la commande `/link`.")
        return
        
    puuid, game_name, tag_line = account
    
    try:
        # Récupérer la partie en cours
        game_data = await get_active_game(puuid)
        
        if not game_data:
            await interaction.followup.send(f"💤 **{game_name}#{tag_line}** n'est pas en partie actuellement.")
            return
            
        # Analyser les joueurs
        embed = await build_live_embed(game_data, puuid, game_name)
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        logger.exception(f"Erreur lors de la commande /live pour le PUUID {puuid} ({game_name}#{tag_line})")
        await interaction.followup.send("⚠️ Impossible d'interroger la partie en cours pour le moment.")

class MatchScoreboard(discord.ui.View):
    def __init__(self, match_data):
        super().__init__(timeout=None)
        self.match_data = match_data

    @discord.ui.button(label="📊 Voir le classement complet", style=discord.ButtonStyle.secondary)
    async def show_scoreboard(self, interaction: discord.Interaction, button: discord.ui.Button):
        blue_team = []
        red_team = []
        for p in self.match_data['info']['participants']:
            champ_name, _ = ddragon.get_champion_info(p['championId'])
            p_name = p.get('riotIdGameName') or p.get('summonerName', 'Inconnu')
            kills, deaths, assists = p['kills'], p['deaths'], p['assists']
            
            c_emoji = get_champ_emoji(champ_name, "")
            player_str = f"• {c_emoji} **{champ_name}** | {p_name} : {kills}/{deaths}/{assists}"
            
            if p['teamId'] == 100:
                blue_team.append(player_str)
            else:
                red_team.append(player_str)

        embed = discord.Embed(
            title="Voici le classement de la partie !",
            color=discord.Color.dark_grey()
        )
        embed.add_field(name="Équipe Bleue :", value="\n".join(blue_team) if blue_team else "Vide", inline=True)
        embed.add_field(name="Équipe Rouge :", value="\n".join(red_team) if red_team else "Vide", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

@tasks.loop(minutes=2)
async def check_matches():
    users = await get_all_tracked_users()
    if not users: return

    current_date = datetime.now().strftime("%Y-%m-%d")

    for (discord_id, puuid, game_name, tag_line, last_match_id, last_lp, last_active_game_id, daily_lp_diff, daily_lp_date, daily_wins, daily_losses) in users:
        # Reset daily LP diff if new day
        if daily_lp_date != current_date:
            daily_lp_diff = 0
            daily_wins = 0
            daily_losses = 0
            daily_lp_date = current_date
        elif daily_lp_diff is None:
            daily_lp_diff = 0
            daily_wins = 0
            daily_losses = 0

        # 1. Vérifier si le joueur est ACTUELLEMENT en partie pour faire une annonce
        try:
            active_game_data = await get_active_game(puuid)
            if active_game_data:
                current_active_id = str(active_game_data.get('gameId'))
                if current_active_id and current_active_id != last_active_game_id:
                    # Nouvelle partie détectée !
                    embed_live = await build_live_embed(active_game_data, puuid, game_name)
                    
                    await update_user_active_match(discord_id, current_active_id)
                    
                    for guild in bot.guilds:
                        if guild.get_member(discord_id):
                            channel_id = await get_guild_tracking_channel(guild.id)
                            if channel_id:
                                channel = bot.get_channel(channel_id)
                                if channel:
                                    await channel.send(embed=embed_live)
        except Exception as e:
            logger.exception(f"Erreur tracking live game pour {game_name}#{tag_line} (PUUID: {puuid})\n{e}")

        # 2. Vérifier si le joueur a TERMINÉ une partie (Historique)
        try:
            latest_match_id = await get_latest_match_id(puuid)
            if not latest_match_id or latest_match_id == last_match_id:
                continue

            match_data = await get_match_details(latest_match_id)
            if not match_data: continue

            # Recherche du joueur dans la game
            participant = next((p for p in match_data['info']['participants'] if p['puuid'] == puuid), None)
            if not participant: continue

            win = participant['win']
            kills = participant['kills']
            deaths = participant['deaths']
            assists = participant['assists']
            game_duration = match_data['info']['gameDuration'] // 60
            champ_name, champ_icon = ddragon.get_champion_info(participant['championId'])
            
            queue_id = match_data['info'].get('queueId', 0)
            
            # Nommage du mode de jeu
            queue_name = "Mode Inconnu"
            if queue_id == 420: queue_name = "Classé Solo/Duo"
            elif queue_id == 440: queue_name = "Classé Flex"
            elif queue_id in (400, 430, 490): queue_name = "Partie Normale"
            elif queue_id == 450: queue_name = "ARAM"
            elif queue_id in (1700, 1710): queue_name = "Arena"

            result_str = "gagné" if win else "perdu"
            color = discord.Color.green() if win else discord.Color.red()

            lp_str = ""
            current_lp = None
            
            # Uniquement pour les parties classées
            if queue_id in (420, 440):
                league_entries = await get_league_entries(puuid)
                queue_type = 'RANKED_SOLO_5x5' if queue_id == 420 else 'RANKED_FLEX_SR'
                
                if league_entries:
                    ranked_queue = next((entry for entry in league_entries if entry['queueType'] == queue_type), None)
                    if ranked_queue:
                        current_lp = ranked_queue['leaguePoints']
                        tier = ranked_queue['tier'].capitalize()
                        rank = ranked_queue['rank']
                        
                        if win:
                            daily_wins = (daily_wins or 0) + 1
                        else:
                            daily_losses = (daily_losses or 0) + 1
                        
                        if last_lp is not None:
                            diff = current_lp - last_lp
                            lp_suffix = f"(+{diff} LP)" if diff >= 0 else f"({diff} LP)"
                            lp_str = f"| {tier} {rank} {lp_suffix} | Total: {current_lp} LP"
                            daily_lp_diff += diff
                        else:
                            lp_str = f"| {tier} {rank} | Total: {current_lp} LP"
                            
            # update_user_match prend 'None' pour current_lp si on est en normal, ce qui ne réécrira pas les anciens LP !
            if current_lp is not None:
                await update_user_match(discord_id, latest_match_id, current_lp, daily_lp_diff, daily_lp_date, daily_wins, daily_losses)
            else:
                await update_user_match(discord_id, latest_match_id, None, None, None, None, None)

            c_emoji = get_champ_emoji(champ_name, "")
            description_text = f"{c_emoji} **{game_name}** vient de **{result_str}**"
            if lp_str:
                description_text += f"\n🏆 {lp_str}"

            embed = discord.Embed(
                title=f"🎮 {queue_name}",
                description=description_text,
                color=color
            )
            embed.set_thumbnail(url=champ_icon)
            embed.add_field(name="Score", value=f"{kills}/{deaths}/{assists}", inline=True)
            embed.add_field(name="Champion", value=f"{c_emoji} {champ_name}", inline=True)
            embed.add_field(name="Temps", value=f"{game_duration}m", inline=True)

            # Envoi dans tous les serveurs où le joueur est et qui ont un tracking channel
            for guild in bot.guilds:
                member = guild.get_member(discord_id)
                if member:
                    channel_id = await get_guild_tracking_channel(guild.id)
                    if channel_id:
                        channel = bot.get_channel(channel_id)
                        if channel:
                            view = MatchScoreboard(match_data)
                            await channel.send(embed=embed, view=view)
        except Exception as e:
            logger.exception(f"Erreur tracking post-match (Historique) pour {game_name}#{tag_line} (PUUID: {puuid})\n{e}")

        # Temporisation pour respecter les Rate Limits de l'API Riot (max 20 req / seconde)
        await asyncio.sleep(1.5)

@check_matches.before_loop
async def before_check_matches():
    await bot.wait_until_ready()

@tasks.loop(hours=1)
async def hourly_recap():
    users = await get_all_tracked_users()
    if not users: return
    
    current_date = datetime.now().strftime("%Y-%m-%d")
    
    for guild in bot.guilds:
        channel_id = await get_guild_tracking_channel(guild.id)
        if not channel_id:
            continue
            
        channel = bot.get_channel(channel_id)
        if not channel:
            continue
            
        recap_lines = []
        for (discord_id, puuid, game_name, tag_line, last_match_id, last_lp, last_active_game_id, daily_lp_diff, daily_lp_date, daily_wins, daily_losses) in users:
            member = guild.get_member(discord_id)
            if member:
                # Si le jour est différent, on réinitialise visuellement à 0 pour l'affichage du récapitulatif
                if daily_lp_date != current_date:
                    daily_lp_diff = 0
                    daily_wins = 0
                    daily_losses = 0
                elif daily_lp_diff is None:
                    daily_lp_diff = 0
                # Fetch highest rank to display icon
                league_entries = await get_league_entries(puuid)
                tier = "Iron" # default
                if league_entries:
                    # try to get highest tier between solo and flex, simplified here to grabbing the first available
                    solo_data = next((q for q in league_entries if q['queueType'] == "RANKED_SOLO_5x5"), None)
                    flex_data = next((q for q in league_entries if q['queueType'] == "RANKED_FLEX_SR"), None)
                    best_data = solo_data or flex_data
                    if best_data:
                        tier = best_data['tier'].capitalize()

                emoji = RANK_EMOJIS.get(tier, "�")
                arrow = "🟢" if daily_lp_diff >= 0 else "�" # using basic directional circle emojis as arrows 
                # (User's image has green up arrow, this approximates it since we don't have custom up arrow)
                # the actual image has <a:up:id>, but we'll use a standard green circle or arrow
                arrow = "➖" # Neutral
                if daily_lp_diff > 0:
                    arrow = "🔼"
                elif daily_lp_diff < 0:
                    arrow = "🔽"
                
                prefix = "+" if daily_lp_diff > 0 else ""
                w = daily_wins or 0
                l = daily_losses or 0
                
                # Format exactly as requested
                line = f"• {emoji} **{game_name}#{tag_line}** : Win: `{w}` | Lose: `{l}` | **{prefix}{daily_lp_diff} LP** {arrow}\n──────────────────────"
                recap_lines.append(line)
                
        if recap_lines:
            embed = discord.Embed(
                title="� Voici le résumé des parties d'aujourd'hui !",
                description="\n\n" + "\n\n".join(recap_lines),
                color=discord.Color.dark_theme()
            )
            embed.set_footer(text=f"Aujourd'hui à {datetime.now().strftime('%H:%M')}")
            await channel.send(embed=embed)

@hourly_recap.before_loop
async def before_hourly_recap():
    await bot.wait_until_ready()

@bot.tree.command(name="setchannel", description="(Admin) Définit le salon courant comme canal d'annonces des fins de parties.")
@app_commands.default_permissions(administrator=True)
async def set_channel(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    if not interaction.guild:
        await interaction.followup.send("❌ Cette commande doit être utilisée dans un serveur.")
        return
        
    await set_guild_tracking_channel(interaction.guild_id, interaction.channel_id)
    await interaction.followup.send(f"✅ C'est noté ! Les résultats de fin de partie des membres de ce serveur seront affichés ici : {interaction.channel.mention}")

@bot.tree.command(name="recap", description="Affiche le récapitulatif journalier des LP des joueurs de ce serveur.")
async def recap(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    
    users = await get_all_tracked_users()
    if not users:
        await interaction.followup.send("Aucun joueur n'est actuellement suivi.")
        return
        
    current_date = datetime.now().strftime("%Y-%m-%d")
    guild = interaction.guild
    
    if not guild:
        await interaction.followup.send("❌ Cette commande ne peut être utilisée que dans un serveur.")
        return
        
    recap_lines = []
    for (discord_id, puuid, game_name, tag_line, last_match_id, last_lp, last_active_game_id, daily_lp_diff, daily_lp_date, daily_wins, daily_losses) in users:
        member = guild.get_member(discord_id)
        if member:
            if daily_lp_date != current_date:
                daily_lp_diff = 0
                daily_wins = 0
                daily_losses = 0
            elif daily_lp_diff is None:
                daily_lp_diff = 0
            league_entries = await get_league_entries(puuid)
            tier = "Iron" # default
            if league_entries:
                solo_data = next((q for q in league_entries if q['queueType'] == "RANKED_SOLO_5x5"), None)
                flex_data = next((q for q in league_entries if q['queueType'] == "RANKED_FLEX_SR"), None)
                best_data = solo_data or flex_data
                if best_data:
                    tier = best_data['tier'].capitalize()

            emoji = RANK_EMOJIS.get(tier, "🟤")
            arrow = "�" if daily_lp_diff >= 0 else "�"
            
            prefix = "+" if daily_lp_diff > 0 else ""
            w = daily_wins or 0
            l = daily_losses or 0
            
            line = f"• {emoji} **{game_name}#{tag_line}** : Win: `{w}` | Lose: `{l}` | **{prefix}{daily_lp_diff} LP** {arrow}\n──────────────────────"
            recap_lines.append(line)
            
    if recap_lines:
        embed = discord.Embed(
            title="� Voici le résumé des parties d'aujourd'hui !",
            description="\n\n" + "\n\n".join(recap_lines),
            color=discord.Color.dark_theme()
        )
        embed.set_footer(text=f"Aujourd'hui à {datetime.now().strftime('%H:%M')}")
        await interaction.followup.send(embed=embed)
    else:
        await interaction.followup.send(f"Aucun changement de LP enregistré pour aujourd'hui sur ce serveur ({current_date}).")

if __name__ == "__main__":
    if not TOKEN or TOKEN == "votre_token_ici":
        logger.critical("Erreur: Le token Discord n'est pas configuré dans le fichier .env")
    else:
        bot.run(TOKEN)
