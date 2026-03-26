import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from datetime import datetime, timezone, timedelta

ECONOMY_FILE = "economy_data.json"

# ============================================================
# ตั้งค่า
# ============================================================
COINS_PER_MESSAGE = 2          # เหรียญต่อข้อความ
COINS_PER_VOICE_MINUTE = 1     # เหรียญต่อนาทีในห้องเสียง
MESSAGE_COOLDOWN = 60          # วินาที cooldown ต่อข้อความ
VOICE_CHECK_INTERVAL = 60      # เช็คห้องเสียงทุกกี่วินาที

# ============================================================
# Helper
# ============================================================
def load_economy() -> dict:
    if os.path.exists(ECONOMY_FILE):
        with open(ECONOMY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_economy(data: dict):
    with open(ECONOMY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user(data: dict, guild_id: int, user_id: int) -> dict:
    gid, uid = str(guild_id), str(user_id)
    data.setdefault(gid, {}).setdefault(uid, {"coins": 0, "last_message": None})
    return data[gid][uid]

def get_coins(guild_id: int, user_id: int) -> int:
    data = load_economy()
    return get_user(data, guild_id, user_id)["coins"]

def add_coins(guild_id: int, user_id: int, amount: int) -> int:
    data = load_economy()
    user = get_user(data, guild_id, user_id)
    user["coins"] = max(0, user["coins"] + amount)
    save_economy(data)
    return user["coins"]

def spend_coins(guild_id: int, user_id: int, amount: int) -> bool:
    """ลดเหรียญ คืน True ถ้าสำเร็จ"""
    data = load_economy()
    user = get_user(data, guild_id, user_id)
    if user["coins"] < amount:
        return False
    user["coins"] -= amount
    save_economy(data)
    return True

# ============================================================
# Cog
# ============================================================
class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._voice_task = None

    async def cog_load(self):
        self._voice_task = self.bot.loop.create_task(self._voice_coin_loop())

    async def cog_unload(self):
        if self._voice_task:
            self._voice_task.cancel()

    # ── ให้เหรียญจากการคุย ────────────────────────────────────
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        data = load_economy()
        user = get_user(data, message.guild.id, message.author.id)
        now = datetime.now(timezone.utc).isoformat()

        # Cooldown
        last = user.get("last_message")
        if last:
            diff = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds()
            if diff < MESSAGE_COOLDOWN:
                return

        user["coins"] += COINS_PER_MESSAGE
        user["last_message"] = now
        save_economy(data)

    # ── ให้เหรียญจากห้องเสียง (loop ทุก 1 นาที) ──────────────
    async def _voice_coin_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            import asyncio
            await asyncio.sleep(VOICE_CHECK_INTERVAL)
            for guild in self.bot.guilds:
                for vc in guild.voice_channels:
                    for member in vc.members:
                        if not member.bot:
                            add_coins(guild.id, member.id, COINS_PER_VOICE_MINUTE)

    # ── /coins — ดูเหรียญ ─────────────────────────────────────
    @app_commands.command(name="coins", description="ดูจำนวนเหรียญของคุณ")
    async def coins(self, interaction: discord.Interaction):
        total = get_coins(interaction.guild_id, interaction.user.id)
        embed = discord.Embed(
            title="💰 เหรียญของคุณ",
            description=f"{interaction.user.mention} มี **{total:,}** เหรียญ",
            color=discord.Color.yellow(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /give_coins — Admin ให้เหรียญ ─────────────────────────
    @app_commands.command(name="give_coins", description="ให้เหรียญสมาชิก (เฉพาะ Admin)")
    @app_commands.describe(member="สมาชิก", amount="จำนวนเหรียญ")
    @app_commands.default_permissions(administrator=True)
    async def give_coins(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if amount <= 0:
            await interaction.response.send_message("❌ จำนวนต้องมากกว่า 0", ephemeral=True)
            return
        new_total = add_coins(interaction.guild_id, member.id, amount)
        await interaction.response.send_message(
            f"✅ ให้ **{amount:,}** เหรียญแก่ {member.mention} แล้ว (รวม {new_total:,} เหรียญ)",
            ephemeral=True,
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))