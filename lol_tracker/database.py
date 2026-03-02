import aiosqlite
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "tracker.db")

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                discord_id INTEGER PRIMARY KEY,
                puuid TEXT NOT NULL,
                game_name TEXT NOT NULL,
                tag_line TEXT NOT NULL,
                last_match_id TEXT,
                last_lp INTEGER,
                last_active_game_id TEXT
            )
        ''')
        
        # Mettre à jour la base de données existante (migration sauvage)
        try:
            await db.execute('ALTER TABLE users ADD COLUMN last_match_id TEXT')
        except Exception:
            pass
        try:
            await db.execute('ALTER TABLE users ADD COLUMN last_lp INTEGER')
        except Exception:
            pass
        try:
            await db.execute('ALTER TABLE users ADD COLUMN last_active_game_id TEXT')
        except Exception:
            pass
        try:
            await db.execute('ALTER TABLE users ADD COLUMN daily_lp_diff INTEGER DEFAULT 0')
        except Exception:
            pass
        try:
            await db.execute('ALTER TABLE users ADD COLUMN daily_lp_date TEXT')
        except Exception:
            pass
        try:
            await db.execute('ALTER TABLE users ADD COLUMN daily_wins INTEGER DEFAULT 0')
        except Exception:
            pass
        try:
            await db.execute('ALTER TABLE users ADD COLUMN daily_losses INTEGER DEFAULT 0')
        except Exception:
            pass

        await db.execute('''
            CREATE TABLE IF NOT EXISTS guild_config (
                guild_id INTEGER PRIMARY KEY,
                tracking_channel_id INTEGER
            )
        ''')
        await db.commit()

async def link_account(discord_id: int, puuid: str, game_name: str, tag_line: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO users (discord_id, puuid, game_name, tag_line)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(discord_id) DO UPDATE SET
                puuid = excluded.puuid,
                game_name = excluded.game_name,
                tag_line = excluded.tag_line
        ''', (discord_id, puuid, game_name, tag_line))
        await db.commit()

async def get_account(discord_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT puuid, game_name, tag_line FROM users WHERE discord_id = ?', (discord_id,)) as cursor:
            return await cursor.fetchone()

async def unlink_account(discord_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM users WHERE discord_id = ?', (discord_id,))
        await db.commit()

async def get_all_accounts():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT discord_id, game_name, tag_line FROM users') as cursor:
            return await cursor.fetchall()
            
async def get_all_tracked_users():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT discord_id, puuid, game_name, tag_line, last_match_id, last_lp, last_active_game_id, daily_lp_diff, daily_lp_date, daily_wins, daily_losses FROM users') as cursor:
            return await cursor.fetchall()

async def update_user_active_match(discord_id: int, active_game_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE users SET last_active_game_id = ? WHERE discord_id = ?', (active_game_id, discord_id))
        await db.commit()

async def update_user_match(discord_id: int, match_id: str, lp: int = None, daily_lp_diff: int = None, daily_lp_date: str = None, daily_wins: int = None, daily_losses: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        if lp is not None and daily_lp_diff is not None and daily_lp_date is not None:
            await db.execute('UPDATE users SET last_match_id = ?, last_lp = ?, daily_lp_diff = ?, daily_lp_date = ?, daily_wins = ?, daily_losses = ? WHERE discord_id = ?', (match_id, lp, daily_lp_diff, daily_lp_date, daily_wins, daily_losses, discord_id))
        elif lp is not None:
            await db.execute('UPDATE users SET last_match_id = ?, last_lp = ? WHERE discord_id = ?', (match_id, lp, discord_id))
        else:
            await db.execute('UPDATE users SET last_match_id = ? WHERE discord_id = ?', (match_id, discord_id))
        await db.commit()

async def get_guild_tracking_channel(guild_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT tracking_channel_id FROM guild_config WHERE guild_id = ?', (guild_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else None

async def set_guild_tracking_channel(guild_id: int, channel_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO guild_config (guild_id, tracking_channel_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET tracking_channel_id = excluded.tracking_channel_id
        ''', (guild_id, channel_id))
        await db.commit()
