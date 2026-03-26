import discord
from discord.ext import commands
from discord import app_commands
import json
import os

# milestone_data.json โครงสร้าง:
# {
#   "guild_id": {
#     "milestones": [
#       { "hours": 10, "role_id": 123456, "message": "ยินดีด้วย!" },
#       ...
#     ],
#     "notify_channel_id": 789012,  # ช่องที่จะส่งการแจ้งเตือน
#     "claimed": {                  # เก็บว่า user ได้รับ milestone ไหนไปแล้ว
#       "user_id": [10, 50, 100]
#     }
#   }
# }

MILESTONE_FILE = "milestone_data.json"

def load_milestones() -> dict:
    if os.path.exists(MILESTONE_FILE):
        with open(MILESTONE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_milestones(data: dict):
    with open(MILESTONE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_guild_data(data: dict, guild_id: int) -> dict:
    gid = str(guild_id)
    data.setdefault(gid, {"milestones": [], "notify_channel_id": None, "claimed": {}})
    return data[gid]

# ============================================================
# ฟังก์ชันหลัก — เช็ค milestone หลัง user ออกจากห้องเสียง
# ============================================================
async def check_milestones(bot: commands.Bot, guild: discord.Guild, member: discord.Member, total_seconds: int):
    data = load_milestones()
    guild_data = get_guild_data(data, guild.id)
    milestones = guild_data.get("milestones", [])
    claimed = guild_data.get("claimed", {})
    uid = str(member.id)
    claimed_hours = claimed.get(uid, [])

    total_hours = total_seconds / 3600
    newly_claimed = []

    for ms in milestones:
        ms_hours = ms["hours"]
        if total_hours >= ms_hours and ms_hours not in claimed_hours:
            newly_claimed.append(ms)
            claimed_hours.append(ms_hours)

    if not newly_claimed:
        return

    # บันทึกว่า claim แล้ว
    guild_data["claimed"][uid] = claimed_hours
    save_milestones(data)

    # ดึง notify channel
    channel_id = guild_data.get("notify_channel_id")
    channel = guild.get_channel(channel_id) if channel_id else None

    for ms in newly_claimed:
        ms_hours = ms["hours"]
        role_id = ms.get("role_id")
        custom_msg = ms.get("message", "")

        # ให้ Role ถ้ากำหนดไว้
        if role_id:
            role = guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role, reason=f"Milestone {ms_hours}h")
                except discord.Forbidden:
                    pass

        # แจ้งเตือนใน channel
        if channel:
            embed = discord.Embed(
                title="🎉 Milestone สำเร็จ!",
                color=discord.Color.gold(),
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="สมาชิก", value=member.mention, inline=False)
            embed.add_field(name="Milestone", value=f"⏱️ ครบ **{ms_hours} ชั่วโมง**", inline=False)
            if role_id and guild.get_role(role_id):
                embed.add_field(name="รางวัล", value=f"🎖️ ได้รับ Role {guild.get_role(role_id).mention}", inline=False)
            if custom_msg:
                embed.add_field(name="ข้อความ", value=custom_msg, inline=False)
            try:
                await channel.send(embed=embed)
            except discord.Forbidden:
                pass

# ============================================================
# Cog
# ============================================================
class MilestoneTracker(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /milestone add — เพิ่ม Milestone ────────────────────
    @app_commands.command(name="milestone_add", description="เพิ่ม Milestone (เฉพาะ Admin)")
    @app_commands.describe(
        hours="จำนวนชั่วโมงสะสมที่ต้องครบ",
        role="Role ที่จะได้รับ (ถ้าไม่ระบุ = ไม่มี Role)",
        message="ข้อความแจ้งเตือนพิเศษ (ถ้าไม่ระบุ = ใช้ข้อความเริ่มต้น)",
    )
    @app_commands.default_permissions(administrator=True)
    async def milestone_add(
        self,
        interaction: discord.Interaction,
        hours: int,
        role: discord.Role = None,
        message: str = "",
    ):
        if hours <= 0:
            await interaction.response.send_message("❌ ชั่วโมงต้องมากกว่า 0", ephemeral=True)
            return

        data = load_milestones()
        guild_data = get_guild_data(data, interaction.guild_id)

        # เช็คว่ามี milestone ชั่วโมงนี้แล้วหรือยัง
        for ms in guild_data["milestones"]:
            if ms["hours"] == hours:
                await interaction.response.send_message(f"❌ มี Milestone **{hours}h** อยู่แล้ว", ephemeral=True)
                return

        guild_data["milestones"].append({
            "hours": hours,
            "role_id": role.id if role else None,
            "message": message,
        })
        guild_data["milestones"].sort(key=lambda x: x["hours"])
        save_milestones(data)

        embed = discord.Embed(title="✅ เพิ่ม Milestone สำเร็จ", color=discord.Color.green())
        embed.add_field(name="ชั่วโมง", value=f"⏱️ {hours}h", inline=True)
        embed.add_field(name="Role", value=role.mention if role else "ไม่มี", inline=True)
        embed.add_field(name="ข้อความ", value=message or "ใช้ข้อความเริ่มต้น", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /milestone remove — ลบ Milestone ────────────────────
    @app_commands.command(name="milestone_remove", description="ลบ Milestone (เฉพาะ Admin)")
    @app_commands.describe(hours="ชั่วโมงของ Milestone ที่ต้องการลบ")
    @app_commands.default_permissions(administrator=True)
    async def milestone_remove(self, interaction: discord.Interaction, hours: int):
        data = load_milestones()
        guild_data = get_guild_data(data, interaction.guild_id)
        before = len(guild_data["milestones"])
        guild_data["milestones"] = [ms for ms in guild_data["milestones"] if ms["hours"] != hours]

        if len(guild_data["milestones"]) == before:
            await interaction.response.send_message(f"❌ ไม่พบ Milestone **{hours}h**", ephemeral=True)
            return

        save_milestones(data)
        await interaction.response.send_message(f"✅ ลบ Milestone **{hours}h** แล้ว", ephemeral=True)

    # ── /milestone list — ดูรายการ Milestone ────────────────
    @app_commands.command(name="milestone_list", description="ดูรายการ Milestone ทั้งหมด")
    async def milestone_list(self, interaction: discord.Interaction):
        data = load_milestones()
        guild_data = get_guild_data(data, interaction.guild_id)
        milestones = guild_data.get("milestones", [])

        embed = discord.Embed(title="🏅 รายการ Milestone", color=discord.Color.blurple())

        if not milestones:
            embed.description = "ยังไม่มี Milestone กรุณาให้ Admin เพิ่มด้วย `/milestone_add`"
        else:
            lines = []
            for ms in milestones:
                role = interaction.guild.get_role(ms["role_id"]) if ms.get("role_id") else None
                role_str = role.mention if role else "ไม่มี Role"
                msg_str = f" — {ms['message']}" if ms.get("message") else ""
                lines.append(f"⏱️ **{ms['hours']}h** → {role_str}{msg_str}")
            embed.description = "\n".join(lines)

        channel_id = guild_data.get("notify_channel_id")
        channel = interaction.guild.get_channel(channel_id) if channel_id else None
        embed.set_footer(text=f"แจ้งเตือนใน: #{channel.name}" if channel else "ยังไม่ได้ตั้งช่องแจ้งเตือน")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── /milestone setchannel — ตั้งช่องแจ้งเตือน ───────────
    @app_commands.command(name="milestone_setchannel", description="ตั้งช่องแจ้งเตือน Milestone (เฉพาะ Admin)")
    @app_commands.describe(channel="ช่องที่ต้องการให้แจ้งเตือน")
    @app_commands.default_permissions(administrator=True)
    async def milestone_setchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        data = load_milestones()
        guild_data = get_guild_data(data, interaction.guild_id)
        guild_data["notify_channel_id"] = channel.id
        save_milestones(data)
        await interaction.response.send_message(
            f"✅ ตั้งช่องแจ้งเตือนเป็น {channel.mention} แล้ว", ephemeral=True
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(MilestoneTracker(bot))