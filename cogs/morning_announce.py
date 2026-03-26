import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime
import zoneinfo
import json
import os

# ============================================================
# ตั้งค่า — แก้ตรงนี้
# ============================================================
CHANNEL_ID      = 123456789012345678   # ID ช่อง announcements
ANNOUNCE_HOUR   = 8
ANNOUNCE_MINUTE = 0
TIMEZONE        = "Asia/Bangkok"
TOP_N           = 5                    # จำนวนอันดับที่แสดง
# ============================================================

DATA_FILE    = "voice_time_data.json"
ECONOMY_FILE = "economy_data.json"

def load_json(path: str) -> dict:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def seconds_to_hms(total: int) -> tuple[int, int, int]:
    return total // 3600, (total % 3600) // 60, total % 60

class MorningAnnounce(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.morning_announce.start()
        print("🌅 MorningAnnounce Cog โหลดแล้ว")

    async def cog_unload(self):
        self.morning_announce.cancel()

    # ── สร้าง Embed ───────────────────────────────────────────
    async def build_embed(self, guild: discord.Guild) -> discord.Embed:
        tz  = pytz.timezone(TIMEZONE)
        now = datetime.now(tz)
        date_str = now.strftime("%A, %d %B %Y")

        embed = discord.Embed(
            title       = "🌅 อรุณสวัสดิ์! สรุปประจำวัน",
            description = f"📅 **{date_str}**\nนี่คือสรุปกิจกรรมของเซิร์ฟเวอร์วานนี้ 👇",
            color       = 0xFFD700,
            timestamp   = datetime.now(tz),
        )

        gid = str(guild.id)
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]

        # ── Top Voice Time ────────────────────────────────────
        voice_data = load_json(DATA_FILE).get(gid, {})
        voice_scores = sorted(voice_data.items(), key=lambda x: x[1], reverse=True)[:TOP_N]

        voice_lines = []
        for i, (uid_str, secs) in enumerate(voice_scores):
            h, m, s = seconds_to_hms(secs)
            member = guild.get_member(int(uid_str))
            if member is None:
                try:
                    member = await guild.fetch_member(int(uid_str))
                except discord.NotFound:
                    pass
            name = member.display_name if member else "(ออกจาก server แล้ว)"
            voice_lines.append(f"{medals[i]} **{name}** — {h}h {m}m {s}s")

        embed.add_field(
            name   = "🎙️ Top Voice Time",
            value  = "\n".join(voice_lines) if voice_lines else "ยังไม่มีข้อมูล",
            inline = False,
        )

        embed.add_field(name="\u200b", value="", inline=False)  # spacer

        # ── Top Coins ─────────────────────────────────────────
        economy_data = load_json(ECONOMY_FILE).get(gid, {})
        coin_scores = sorted(
            economy_data.items(),
            key=lambda x: x[1].get("coins", 0) if isinstance(x[1], dict) else x[1],
            reverse=True,
        )[:TOP_N]

        coin_lines = []
        for i, (uid_str, user_data) in enumerate(coin_scores):
            coins = user_data.get("coins", 0) if isinstance(user_data, dict) else user_data
            member = guild.get_member(int(uid_str))
            if member is None:
                try:
                    member = await guild.fetch_member(int(uid_str))
                except discord.NotFound:
                    pass
            name = member.display_name if member else "(ออกจาก server แล้ว)"
            coin_lines.append(f"{medals[i]} **{name}** — {coins:,} 🪙")

        embed.add_field(
            name   = "💰 Top Coins",
            value  = "\n".join(coin_lines) if coin_lines else "ยังไม่มีข้อมูล",
            inline = False,
        )

        embed.set_footer(text="อัปเดตทุกเช้า 08:00 น. • ขยันเข้าห้องเสียงและแชทเพื่อสะสมคะแนน!")
        return embed

    # ── Task: ส่งทุกเช้า ──────────────────────────────────────
    @tasks.loop(minutes=1)
    async def morning_announce(self):
        tz  = pytz.timezone(TIMEZONE)
        now = datetime.now(tz)
        if now.hour != ANNOUNCE_HOUR or now.minute != ANNOUNCE_MINUTE:
            return

        channel = self.bot.get_channel(CHANNEL_ID)
        if channel is None:
            print(f"[MorningAnnounce] ไม่พบ Channel ID: {CHANNEL_ID}")
            return

        embed = await self.build_embed(channel.guild)
        await channel.send(embed=embed)
        print(f"[MorningAnnounce] ✅ ส่งแล้ว {now.strftime('%Y-%m-%d %H:%M')}")

    @morning_announce.before_loop
    async def before_loop(self):
        await self.bot.wait_until_ready()

    # ── /morningnow — Admin สั่ง preview ทันที ───────────────
    @app_commands.command(name="morningnow", description="Preview Morning Announcement (เฉพาะ Admin)")
    @app_commands.default_permissions(administrator=True)
    async def morningnow(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        embed = await self.build_embed(interaction.guild)
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(MorningAnnounce(bot))