import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv

# --- โหลด Token ---
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# โหลด Cog ตามลำดับที่กำหนด (สำคัญ — economy ต้องมาก่อน pet และ game)
COG_ORDER = [
    "economy",   # ระบบเหรียญ (ต้องโหลดก่อนสุด)
    "timeing",   # ระบบนับเวลา voice
    "milestone", # ระบบ milestone (ต้องมาหลัง timeing)
    "pet",       # ระบบสัตว์เลี้ยง (ต้องมาหลัง economy)
    "game",      # เกมทายคำ (ต้องมาหลัง economy)
    "verify",    # ระบบ verify
    "voiceroom", # ระบบสร้างห้องชั่วคราว
]

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True        # ← เพิ่มตรงนี้
        intents.voice_states = True   # ← เพิ่มตรงนี้
        super().__init__(command_prefix=".", intents=intents)

    async def setup_hook(self):
        loaded = set()

        # โหลดตามลำดับที่กำหนดก่อน
        for name in COG_ORDER:
            filename = f"{name}.py"
            path = f"./cogs/{filename}"
            if os.path.exists(path):
                try:
                    await self.load_extension(f"cogs.{name}")
                    loaded.add(filename)
                    print(f"✅ Loaded Cog: {filename}")
                except Exception as e:
                    print(f"❌ Failed to load Cog {filename}: {e}")

        # โหลดที่เหลือที่ไม่ได้อยู่ใน COG_ORDER
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py") and filename not in loaded:
                try:
                    await self.load_extension(f"cogs.{filename[:-3]}")
                    print(f"✅ Loaded Cog: {filename}")
                except Exception as e:
                    print(f"❌ Failed to load Cog {filename}: {e}")

        await self.tree.sync()
        print(f"🚀 {self.user.name} is Online and Synced!")

bot = MyBot()

@bot.event
async def on_ready():
    print("-------------------------")
    print(f"Logged in as {bot.user}")
    print("-------------------------")

async def main():
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())