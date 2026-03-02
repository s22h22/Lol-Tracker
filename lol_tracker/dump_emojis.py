import os
import discord
import asyncio
from dotenv import load_dotenv

load_dotenv()

class MyClient(discord.Client):
    async def on_ready(self):
        emojis = await self.fetch_application_emojis()
        
        with open("emojis.py", "w", encoding="utf-8") as f:
            f.write("CHAMP_EMOJIS = {\n")
            # We skip Season_2023__ because those are ranks
            for e in emojis:
                if "Season_2023" not in e.name:
                    f.write(f'    "{e.name}": "<:{e.name}:{e.id}>",\n')
            f.write("}\n")
            
        print(f"Dumped {len(emojis)} total App Emojis to emojis.py!")
        await self.close()

client = MyClient(intents=discord.Intents.default())
client.run(os.getenv('DISCORD_TOKEN'))
