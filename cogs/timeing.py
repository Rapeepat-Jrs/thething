import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from datetime import datetime
from cogs.milestone import check_milestones

DATA_FILE = "voice_time_data.json"
SESSION_FILE = "voice_sessions.json"  # เก็บ active sessions ตอน bot ปิด

active_sessions: dict[str, datetime] = {}

# ============================================================
# Helper Functions
# ============================================================
def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def save_sessions():
    """บันทึก active sessions ลงไฟล์ (ตอน bot ปิด)"""
    serialized = {k: v.isoformat() for k, v in active_sessions.items()}
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(serialized, f, ensure_ascii=False, indent=2)

def load_sessions():
    """โหลด active sessions กลับมา (ตอน bot เปิด)"""
    if not os.path.exists(SESSION_FILE):
        return
    with open(SESSION_FILE, "r", encoding="utf-8") as f:
        serialized = json.load(f)
    for k, v in serialized.items():
        active_sessions[k] = datetime.fromisoformat(v)
    os.remove(SESSION_FILE)  # ลบไฟล์หลังโหลดแล้ว
    print(f"♻️ โหลด {len(active_sessions)} active session(s) กลับมา")

def user_key(guild_id: int, user_id: int) -> str:
    return f"{guild_id}:{user_id}"

def seconds_to_hms(total_seconds: int) -> tuple[int, int, int]:
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    return h, m, s

def format_duration(total_seconds: int) -> str:
    h, m, s = seconds_to_hms(total_seconds)
    parts = []
    if h:
        parts.append(f"**{h}** ชั่วโมง")
    if m:
        parts.append(f"**{m}** นาที")
    parts.append(f"**{s}** วินาที")
    return " ".join(parts) if parts else "**0** วินาที"

def get_total_seconds(data: dict, guild_id: int, user_id: int) -> int:
    key = user_key(guild_id, user_id)
    saved = data.get(str(guild_id), {}).get(str(user_id), 0)
    if key in active_sessions:
        saved += int((datetime.utcnow() - active_sessions[key]).total_seconds())
    return saved

def add_seconds(data: dict, guild_id: int, user_id: int, seconds: int):
    gid, uid = str(guild_id), str(user_id)
    data.setdefault(gid, {})[uid] = data.get(gid, {}).get(uid, 0) + seconds

# ============================================================
# Cog
# ============================================================
class VoiceTracker(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        """โหลด sessions ที่ค้างอยู่ตอน bot restart"""
        load_sessions()

    async def cog_unload(self):
        """บันทึก active sessions ทั้งหมดก่อน bot ปิด"""
        save_sessions()
        print(f"💾 บันทึก {len(active_sessions)} active session(s) แล้ว")

    # ── ติดตามทุกคนที่เข้า-ออกห้องเสียง ──────────────────────
    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ):
        key = user_key(member.guild.id, member.id)

        # เข้าห้องเสียง
        if after.channel is not None and before.channel is None:
            active_sessions[key] = datetime.utcnow()
            print(f"🎙️ {member.display_name} เข้าห้อง '{after.channel.name}'")

        # ออกจากห้องเสียง
        elif after.channel is None and before.channel is not None:
            if key in active_sessions:
                elapsed = int((datetime.utcnow() - active_sessions.pop(key)).total_seconds())
                data = load_data()
                add_seconds(data, member.guild.id, member.id, elapsed)
                save_data(data)
                h, m, s = seconds_to_hms(elapsed)
                print(f"📤 {member.display_name} ออกจากห้อง — session: {h}h {m}m {s}s")
                total = get_total_seconds(load_data(), member.guild.id, member.id)
                await check_milestones(self.bot, member.guild, member, total)

    # ── /voicetime — ดูเวลาตัวเอง ─────────────────────────────
    @app_commands.command(name="voicetime", description="ดูเวลาที่คุณใช้ใน Discord")
    async def voicetime(self, interaction: discord.Interaction):
        user = interaction.user
        data = load_data()
        total = get_total_seconds(data, interaction.guild_id, user.id)

        embed = discord.Embed(
            title="🎙️ เวลาของคุณใน Discord",
            color=discord.Color.green() if total > 0 else discord.Color.grayed_out(),
            timestamp=datetime.utcnow(),
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="เวลารวม", value=format_duration(total), inline=False)

        h, m, s = seconds_to_hms(total)
        embed.add_field(
            name="รายละเอียด",
            value=f"🕐 {h} ชั่วโมง  🕑 {m} นาที  🕒 {s} วินาที",
            inline=False,
        )

        key = user_key(interaction.guild_id, user.id)
        footer = "🟢 กำลังอยู่ในห้องเสียงตอนนี้" if key in active_sessions else "⚫ ไม่ได้อยู่ในห้องเสียง"
        embed.set_footer(text=footer)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /voicetop — อันดับรวมของเซิร์ฟเวอร์ ──────────────────
    @app_commands.command(name="voicetop", description="อันดับผู้ใช้เวลาใน Discord นี้มากที่สุด")
    @app_commands.describe(limit="จำนวนอันดับที่แสดง (1-20, ค่าเริ่มต้น 10)")
    async def voicetop(self, interaction: discord.Interaction, limit: int = 10):
        # defer ก่อนเพราะ fetch_member หลายคนอาจใช้เวลานาน
        await interaction.response.defer(ephemeral=True)

        limit = max(1, min(limit, 20))
        data = load_data()
        gid = str(interaction.guild_id)
        guild_data = data.get(gid, {})

        scores: list[tuple[int, int]] = []
        seen: set[int] = set()

        for uid_str, saved in guild_data.items():
            uid = int(uid_str)
            seen.add(uid)
            key = user_key(interaction.guild_id, uid)
            total = saved
            if key in active_sessions:
                total += int((datetime.utcnow() - active_sessions[key]).total_seconds())
            scores.append((uid, total))

        for key, start in active_sessions.items():
            gid_key, uid_str = key.split(":")
            if int(gid_key) == interaction.guild_id:
                uid = int(uid_str)
                if uid not in seen:
                    elapsed = int((datetime.utcnow() - start).total_seconds())
                    scores.append((uid, elapsed))

        scores.sort(key=lambda x: x[1], reverse=True)
        top = scores[:limit]

        embed = discord.Embed(
            title=f"🏆 อันดับเวลาคนที่ไม่ทำห่าอะไรเลยนอกจากสิงอยู่ใน Discord (Top {limit})",
            color=discord.Color.gold(),
            timestamp=datetime.utcnow(),
        )

        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for rank, (uid, total) in enumerate(top, 1):
            # ลองดึงจาก cache ก่อน ถ้าไม่มีค่อย fetch จาก API
            member = interaction.guild.get_member(uid)
            if member is None:
                try:
                    member = await interaction.guild.fetch_member(uid)
                except discord.NotFound:
                    pass  # ออกจาก server ไปแล้ว
            name = member.display_name if member else "(ออกจาก server แล้ว)"
            h, m, s = seconds_to_hms(total)
            medal = medals[rank - 1] if rank <= 3 else f"**#{rank}**"
            lines.append(f"{medal} {name} — {h}h {m}m {s}s")

        embed.description = "\n".join(lines) if lines else "ยังไม่มีข้อมูล"
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── /voiceedit — แก้ไขเวลา (Admin เท่านั้น) ──────────────
    @app_commands.command(name="voiceedit", description="แก้ไขเวลาของสมาชิก (เฉพาะ Admin)")
    @app_commands.describe(
        member="สมาชิกที่ต้องการแก้ไข",
        mode="set = ตั้งค่าใหม่, add = บวกเพิ่ม, subtract = ลบออก",
        hours="ชั่วโมง",
        minutes="นาที",
        seconds="วินาที",
    )
    @app_commands.choices(mode=[
        app_commands.Choice(name="set — ตั้งค่าใหม่", value="set"),
        app_commands.Choice(name="add — บวกเพิ่ม", value="add"),
        app_commands.Choice(name="subtract — ลบออก", value="subtract"),
    ])
    @app_commands.default_permissions(administrator=True)
    async def voiceedit(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        mode: str,
        hours: int = 0,
        minutes: int = 0,
        seconds: int = 0,
    ):
        delta = hours * 3600 + minutes * 60 + seconds

        if delta == 0 and mode != "set":
            await interaction.response.send_message("❌ กรุณาใส่เวลาที่ต้องการแก้ไข", ephemeral=True)
            return

        data = load_data()
        gid, uid = str(interaction.guild_id), str(member.id)
        current = data.get(gid, {}).get(uid, 0)

        if mode == "set":
            data.setdefault(gid, {})[uid] = delta
            action = "ตั้งค่าเป็น"
        elif mode == "add":
            data.setdefault(gid, {})[uid] = current + delta
            action = "บวกเพิ่ม"
        else:  # subtract
            data.setdefault(gid, {})[uid] = max(0, current - delta)
            action = "ลบออก"

        save_data(data)

        new_total = data[gid][uid]
        h_d, m_d, s_d = seconds_to_hms(delta)

        embed = discord.Embed(
            title="✏️ แก้ไขเวลาสำเร็จ",
            color=discord.Color.blurple(),
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="สมาชิก", value=member.mention, inline=False)
        embed.add_field(name="การแก้ไข", value=f"{action} {h_d}h {m_d}m {s_d}s", inline=False)
        embed.add_field(name="เวลารวมใหม่", value=format_duration(new_total), inline=False)
        embed.set_footer(text=f"แก้ไขโดย {interaction.user.display_name}")

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceTracker(bot))