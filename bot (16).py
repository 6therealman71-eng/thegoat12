import discord
from discord.ext import commands
from discord import app_commands, Embed, Color, Interaction, ui
from discord.ui import View, Button
import datetime
import json
import os
import asyncio
import aiofiles

# ---------------- CONFIG ----------------
TOKEN = os.environ.get("BOT_TOKEN")
GUILD_ID = 1493335493717397574

# Channels
TICKETS_CATEGORY_ID = 1493355935463117020
SUPPORT_CATEGORY_ID = 1493356146721816678
INDEX_CATEGORY_ID = 1493355626099769354
MM_CHANNEL_ID = 1493356007525585089
SUPPORT_CHANNEL_ID = 1493356166565068961
INDEX_CHANNEL_ID = 1493355671389868042
TRANSCRIPT_CHANNEL_ID = 1493373859733311528
BAN_LOG_CHANNEL_ID = 1493373914645270638
PROMO_LOG_CHANNEL_ID = 1493374017946517626
VOUCH_CHANNEL_ID = 1493356029415788786

# Roles
OWNER_ROLE_ID = 1493358595155165365
MIDDLEMAN_ROLE_ID = 1493356508224815135          # Breakfast MM
ESTABLISHED_MM_ROLE_ID = 1493356551744917695     # Lunch MM
MM_MANAGER_ROLE_ID = 1493356780678549674         # Middleman Manager
VOUCHER_ROLE_ID = 1493356446920736986
BAN_PERMS_ROLE_ID = 1493357047541006376
CO_FOUNDER_ROLE_ID = 1493357880441704479
ADMINISTRATOR_ROLE_ID = 1493357340647493843
CHIEF_EX_ROLE_ID = 1493358188865523933
SUPPORT_STAFF_ROLE_ID = 1493382716367044798
SUPPORT_MANAGER_ROLE_ID = 1493382765679218802

# Aliases for clarity
BREAKFAST_MM_ROLE_ID = MIDDLEMAN_ROLE_ID
LUNCH_MM_ROLE_ID = ESTABLISHED_MM_ROLE_ID

WARN_DATA_FILE = "warns.json"
TICKET_DATA_FILE = "tickets.json"
VOUCH_DATA_FILE = "vouches.json"


class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.vouch_data = {}
        self.active_tickets = {}

    async def setup_hook(self):
        await self.load_data()
        guild = discord.Object(id=GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        self.add_view(TicketPanel())
        self.add_view(TicketControls())
        self.add_view(IndexTicketPanel())
        self.add_view(IndexTicketControls())
        self.add_view(SupportTicketPanel())
        self.add_view(SupportTicketControls())
        print(f"Logged in as {self.user}. Commands synced.")

    async def load_data(self):
        try:
            if os.path.exists(VOUCH_DATA_FILE):
                async with aiofiles.open(VOUCH_DATA_FILE, "r") as f:
                    content = await f.read()
                    if content:
                        self.vouch_data = json.loads(content)
            if os.path.exists(TICKET_DATA_FILE):
                async with aiofiles.open(TICKET_DATA_FILE, "r") as f:
                    content = await f.read()
                    if content:
                        self.active_tickets = json.loads(content)
        except Exception as e:
            print(f"Data load error: {e}")

    async def save_data(self):
        async with aiofiles.open(VOUCH_DATA_FILE, "w") as f:
            await f.write(json.dumps(self.vouch_data, indent=4))
        async with aiofiles.open(TICKET_DATA_FILE, "w") as f:
            await f.write(json.dumps(self.active_tickets, indent=4))


bot = MyBot()

# ---------------- PERMISSION HELPERS ----------------
def has_role(member, role_id):
    return any(r.id == role_id for r in member.roles)

def is_mm(interaction: Interaction):
    return has_role(interaction.user, MIDDLEMAN_ROLE_ID)

def is_manager(interaction: Interaction):
    return (
        has_role(interaction.user, MM_MANAGER_ROLE_ID) or
        has_role(interaction.user, CO_FOUNDER_ROLE_ID) or
        has_role(interaction.user, ADMINISTRATOR_ROLE_ID) or
        has_role(interaction.user, OWNER_ROLE_ID)
    )

# Member-based helpers for prefix commands
def is_mm_member(member):
    return has_role(member, MIDDLEMAN_ROLE_ID)

def is_manager_member(member):
    return (
        has_role(member, MM_MANAGER_ROLE_ID) or
        has_role(member, CO_FOUNDER_ROLE_ID) or
        has_role(member, ADMINISTRATOR_ROLE_ID) or
        has_role(member, OWNER_ROLE_ID)
    )


import random

# ================================================================
# RANDOM RATING HELPER
# ================================================================
async def send_random_rating(vouch_ch, owner_id: int, mm_id: int):
    owner_rating = random.randint(3, 5)
    mm_rating = random.randint(3, 5)
    stars_o = "\u2b50" * owner_rating
    stars_m = "\u2b50" * mm_rating
    desc = f"<@{owner_id}> rated the MM service: **{owner_rating}/5** {stars_o}\n<@{mm_id}> rated the ticket owner: **{mm_rating}/5** {stars_m}"
    embed = Embed(title="\u2b50 Trade Rated", description=desc, color=Color.gold(), timestamp=datetime.datetime.now())
    embed.set_footer(text="Powered by Trading Portal \u2022 Today")
    await vouch_ch.send(content=f"<@{owner_id}> <@{mm_id}>", embed=embed)


# Stores recent closed tickets as (owner_id, mm_id) for the loop
recent_closed_tickets = []


# ---------------- WARN HELPERS ----------------
async def load_warns():
    try:
        if os.path.exists(WARN_DATA_FILE):
            async with aiofiles.open(WARN_DATA_FILE, "r") as f:
                content = await f.read()
                if content:
                    return json.loads(content)
    except:
        pass
    return {}

async def save_warns(data):
    async with aiofiles.open(WARN_DATA_FILE, "w") as f:
        await f.write(json.dumps(data, indent=4))

# ---------------- TICKET CLOSE LOGIC ----------------
async def close_ticket_logic(interaction: Interaction):
    tid = str(interaction.channel.id)
    data = bot.active_tickets.get(tid)
    if not data:
        return await interaction.response.send_message("❌ This is not an active ticket channel.", ephemeral=True)
    if (
        not is_mm(interaction)
        and not has_role(interaction.user, ESTABLISHED_MM_ROLE_ID)
        and not has_role(interaction.user, SUPPORT_STAFF_ROLE_ID)
        and not is_manager(interaction)
        and data["owner"] != interaction.user.id
    ):
        return await interaction.response.send_message("❌ Only the claimed MM or the Ticket Owner can close this ticket.", ephemeral=True)

    await interaction.response.send_message("⌛ Archiving chat and closing channel in 5s...")
    log_ch = interaction.guild.get_channel(TRANSCRIPT_CHANNEL_ID)
    msgs = []
    async for msg in interaction.channel.history(limit=None, oldest_first=True):
        if msg.content:
            msgs.append(f"{msg.author}: {msg.content}")
    txt = "\n".join(msgs)
    embed = Embed(title="📜 Ticket Transcript", color=Color.dark_gray(), timestamp=datetime.datetime.now())
    embed.add_field(name="Ticket Owner", value=f"<@{data['owner']}>", inline=True)
    embed.add_field(name="Claimed By", value=f"<@{data['claimed']}>" if data["claimed"] else "Unclaimed", inline=True)
    embed.add_field(name="Closed By", value=interaction.user.mention, inline=True)
    embed.add_field(name="Closed At", value=datetime.datetime.now().strftime("%A, %B %d, %Y %I:%M %p"), inline=False)
    if txt:
        embed.description = txt[:4000]
    if log_ch:
        await log_ch.send(embed=embed)
    bot.active_tickets.pop(tid, None)
    await bot.save_data()

    # Auto-post random rating to vouch channel on ticket close
    vouch_ch = interaction.guild.get_channel(VOUCH_CHANNEL_ID)
    if vouch_ch and data.get("claimed"):
        owner_id = data["owner"]
        mm_id = data["claimed"]
        recent_closed_tickets.append((owner_id, mm_id))
        await send_random_rating(vouch_ch, owner_id, mm_id)

    await asyncio.sleep(5)
    await interaction.channel.delete()


# ================================================================
# MM TICKET
# ================================================================
class TicketPanel(View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="🎫 Open Ticket", style=discord.ButtonStyle.primary, custom_id="persistent:open_ticket")
    async def open_ticket(self, interaction: Interaction, button: Button):
        category = interaction.guild.get_channel(TICKETS_CATEGORY_ID)
        if not category:
            return await interaction.response.send_message("❌ Ticket category configuration missing.", ephemeral=True)
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
            interaction.guild.get_role(MIDDLEMAN_ROLE_ID): discord.PermissionOverwrite(view_channel=True, send_messages=False),
        }
        channel = await interaction.guild.create_text_channel(
            name=f"ticket-{interaction.user.name}",
            category=category,
            overwrites=overwrites
        )
        bot.active_tickets[str(channel.id)] = {"owner": interaction.user.id, "claimed": None}
        await bot.save_data()
        embed = Embed(
            title="🔐 Trusted Middleman Service",
            description=(
                "✅ 100% Trusted & Staff-Handled Trades\n\n"
                "• Your trade is handled by verified Middlemen\n"
                "• Funds/items are secured during the trade\n"
                "• If any scam occurs, refunds are available\n\n"
                "📌 Please provide:\n"
                "• Trade details\n"
                "• User involved\n"
                "• Proof/screenshots\n\n"
                "⬇️ A middleman will claim your ticket shortly."
            ),
            color=Color.blurple()
        )
        embed.set_footer(text="Powered by Trading Portal • Today")
        await channel.send(content=f"{interaction.user.mention} <@&{MIDDLEMAN_ROLE_ID}>", embed=embed, view=TicketControls())
        await interaction.response.send_message(f"✅ Your ticket has been created: {channel.mention}", ephemeral=True)


class TicketControls(View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="🛡️ Claim", style=discord.ButtonStyle.success, custom_id="persistent:claim_ticket")
    async def claim(self, interaction: Interaction, button: Button):
        tid = str(interaction.channel.id)
        data = bot.active_tickets.get(tid)
        if not data:
            return await interaction.response.send_message("❌ This is not an active ticket channel.", ephemeral=True)
        if data["claimed"]:
            return await interaction.response.send_message("❌ This ticket is already claimed.", ephemeral=True)
        if not is_mm(interaction) and not is_manager(interaction):
            return await interaction.response.send_message("❌ Only Verified Middlemen can claim this ticket.", ephemeral=True)
        data["claimed"] = interaction.user.id
        await bot.save_data()
        button.label = "✅ Claimed"
        button.disabled = True
        button.style = discord.ButtonStyle.secondary
        await interaction.channel.set_permissions(interaction.user, send_messages=True, attach_files=True)
        embed = interaction.message.embeds[0]
        embed.add_field(name="Claimed By", value=interaction.user.mention, inline=False)
        await interaction.response.edit_message(embed=embed, view=self)

        # Send claimed embed as a new message
        claimed_embed = Embed(
            title="✅ Ticket Claimed",
            description=f"{interaction.user.mention} will be your Middleman for today.",
            color=Color.green(),
            timestamp=datetime.datetime.now()
        )
        claimed_embed.set_footer(text="Powered by Trading Portal • Today")
        await interaction.channel.send(embed=claimed_embed)

    @ui.button(label="🔒 Close", style=discord.ButtonStyle.danger, custom_id="persistent:close_ticket")
    async def close(self, interaction: Interaction, button: Button):
        await close_ticket_logic(interaction)


# ================================================================
# INDEX TICKET
# ================================================================
class IndexTicketPanel(View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="📋 Open Index Ticket", style=discord.ButtonStyle.primary, custom_id="persistent:open_index_ticket")
    async def open_index_ticket(self, interaction: Interaction, button: Button):
        category = interaction.guild.get_channel(INDEX_CATEGORY_ID)
        if not category:
            return await interaction.response.send_message("❌ Index category configuration missing.", ephemeral=True)
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
            interaction.guild.get_role(ESTABLISHED_MM_ROLE_ID): discord.PermissionOverwrite(view_channel=True, send_messages=False),
        }
        channel = await interaction.guild.create_text_channel(
            name=f"index-{interaction.user.name}",
            category=category,
            overwrites=overwrites
        )
        bot.active_tickets[str(channel.id)] = {"owner": interaction.user.id, "claimed": None}
        await bot.save_data()
        embed = Embed(
            title="📋 Index Ticket",
            description=(
                "✅ Professional Index MM Service\n\n"
                "• One of our professional Index MMs will be with you shortly\n\n"
                "📌 Available Bases:\n"
                "• Divine Base\n"
                "• Cursed Base\n"
                "• Ying Yang Base\n"
                "• Candy Base\n"
                "• Galaxy Base\n"
                "• Lava Base\n"
                "• Rainbow Base\n"
                "• And more!\n\n"
                "⬇️ An Index MM will claim your ticket shortly."
            ),
            color=Color.gold()
        )
        embed.set_footer(text="Powered by Trading Portal • Today")
        await channel.send(content=f"{interaction.user.mention} <@&{ESTABLISHED_MM_ROLE_ID}>", embed=embed, view=IndexTicketControls())
        await interaction.response.send_message(f"✅ Your index ticket has been created: {channel.mention}", ephemeral=True)


class IndexTicketControls(View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="🛡️ Claim", style=discord.ButtonStyle.success, custom_id="persistent:claim_index_ticket")
    async def claim(self, interaction: Interaction, button: Button):
        tid = str(interaction.channel.id)
        data = bot.active_tickets.get(tid)
        if not data:
            return await interaction.response.send_message("❌ This is not an active ticket channel.", ephemeral=True)
        if data["claimed"]:
            return await interaction.response.send_message("❌ This ticket is already claimed.", ephemeral=True)
        if not has_role(interaction.user, ESTABLISHED_MM_ROLE_ID) and not is_manager(interaction):
            return await interaction.response.send_message("❌ Only Established MMs can claim this ticket.", ephemeral=True)
        data["claimed"] = interaction.user.id
        await bot.save_data()
        button.label = "✅ Claimed"
        button.disabled = True
        button.style = discord.ButtonStyle.secondary
        await interaction.channel.set_permissions(interaction.user, send_messages=True, attach_files=True)
        embed = interaction.message.embeds[0]
        embed.add_field(name="Claimed By", value=interaction.user.mention, inline=False)
        await interaction.response.edit_message(embed=embed, view=self)

        claimed_embed = Embed(
            title="✅ Ticket Claimed",
            description=f"{interaction.user.mention} will be your Index MM for today.",
            color=Color.green(),
            timestamp=datetime.datetime.now()
        )
        claimed_embed.set_footer(text="Powered by Trading Portal • Today")
        await interaction.channel.send(embed=claimed_embed)

    @ui.button(label="🔒 Close", style=discord.ButtonStyle.danger, custom_id="persistent:close_index_ticket")
    async def close(self, interaction: Interaction, button: Button):
        await close_ticket_logic(interaction)


# ================================================================
# SUPPORT TICKET
# ================================================================
class SupportTicketPanel(View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="🔵 Open a ticket!", style=discord.ButtonStyle.primary, custom_id="persistent:open_support_ticket")
    async def open_support_ticket(self, interaction: Interaction, button: Button):
        category = interaction.guild.get_channel(SUPPORT_CATEGORY_ID)
        if not category:
            return await interaction.response.send_message("❌ Support category configuration missing.", ephemeral=True)
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, attach_files=True),
            interaction.guild.get_role(SUPPORT_STAFF_ROLE_ID): discord.PermissionOverwrite(view_channel=True, send_messages=False),
        }
        channel = await interaction.guild.create_text_channel(
            name=f"support-{interaction.user.name}",
            category=category,
            overwrites=overwrites
        )
        bot.active_tickets[str(channel.id)] = {"owner": interaction.user.id, "claimed": None}
        await bot.save_data()
        embed = Embed(
            title="🔵 Support Ticket",
            description=(
                "✅ A support helper will be with you shortly!\n\n"
                "📌 Please provide:\n"
                "• Your issue or question\n"
                "• Any relevant screenshots or proof\n"
                "• Who was involved if applicable\n\n"
                "⬇️ A support staff member will claim your ticket shortly."
            ),
            color=Color.blue()
        )
        embed.set_footer(text="Powered by Trading Portal • Today")
        await channel.send(content=f"{interaction.user.mention} <@&{SUPPORT_STAFF_ROLE_ID}>", embed=embed, view=SupportTicketControls())
        await interaction.response.send_message(f"✅ Your support ticket has been created: {channel.mention}", ephemeral=True)


class SupportTicketControls(View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="🛡️ Claim", style=discord.ButtonStyle.success, custom_id="persistent:claim_support_ticket")
    async def claim(self, interaction: Interaction, button: Button):
        tid = str(interaction.channel.id)
        data = bot.active_tickets.get(tid)
        if not data:
            return await interaction.response.send_message("❌ This is not an active ticket channel.", ephemeral=True)
        if data["claimed"]:
            return await interaction.response.send_message("❌ This ticket is already claimed.", ephemeral=True)
        if not has_role(interaction.user, SUPPORT_STAFF_ROLE_ID) and not has_role(interaction.user, SUPPORT_MANAGER_ROLE_ID) and not is_manager(interaction):
            return await interaction.response.send_message("❌ Only Support Staff can claim this ticket.", ephemeral=True)
        data["claimed"] = interaction.user.id
        await bot.save_data()
        button.label = "✅ Claimed"
        button.disabled = True
        button.style = discord.ButtonStyle.secondary
        await interaction.channel.set_permissions(interaction.user, send_messages=True, attach_files=True)
        embed = interaction.message.embeds[0]
        embed.add_field(name="Claimed By", value=interaction.user.mention, inline=False)
        await interaction.response.edit_message(embed=embed, view=self)

        claimed_embed = Embed(
            title="✅ Ticket Claimed",
            description=f"{interaction.user.mention} will be your Support Staff for today.",
            color=Color.green(),
            timestamp=datetime.datetime.now()
        )
        claimed_embed.set_footer(text="Powered by Trading Portal • Today")
        await interaction.channel.send(embed=claimed_embed)

    @ui.button(label="🔒 Close", style=discord.ButtonStyle.danger, custom_id="persistent:close_support_ticket")
    async def close(self, interaction: Interaction, button: Button):
        await close_ticket_logic(interaction)


# ================================================================
# MERCY (formerly /info) VIEW
# ================================================================
class MercyView(View):
    def __init__(self, target: discord.Member, author: discord.Member):
        super().__init__(timeout=60.0)
        self.target = target
        self.author = author

    @ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: Interaction, button: Button):
        if interaction.user.id != self.target.id:
            return await interaction.response.send_message("❌ Only the targeted user can respond to this.", ephemeral=True)
        role = interaction.guild.get_role(VOUCHER_ROLE_ID)
        if role:
            await self.target.add_roles(role)

        # Edit the original message to show accepted state
        accepted_embed = Embed(
            title="✅ Opportunity Accepted",
            description=f"{self.target.mention} has accepted the opportunity and has been verified.",
            color=Color.green(),
            timestamp=datetime.datetime.now()
        )
        accepted_embed.set_footer(text="Powered by Trading Portal • Today")

        # Disable both buttons
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=accepted_embed, view=self)

        # DM tutorial
        tutorial_embed = Embed(
            title="💫 Hitting Tutorial",
            description=(
                "You're a hitter now. A hitter is someone that got scammed by us, and goes out to scam others.\n\n"
                "**What do I do?**\n"
                "Go to other Discord servers and advertise that you're looking to trade. When someone DMs you, "
                "guide the conversation towards using a middleman. Once they agree, invite them to this server and open a ticket.\n\n"
                "**How do I get paid?**\n"
                "Once the trade is complete, you and the middleman split the profit 50/50.\n\n"
                "**Can I rank up?**\n"
                "Yes! Check rank-up-info for requirements.\n\n"
                "**Important Rules**\n"
                "Never advertise in DMs and never use a personal middleman. Both result in an instant ban."
            ),
            color=Color.gold(),
            timestamp=datetime.datetime.now()
        )
        tutorial_embed.set_footer(text="Seize the opportunity.")
        try:
            await self.target.send(embed=tutorial_embed)
        except:
            pass

        log_ch = interaction.guild.get_channel(PROMO_LOG_CHANNEL_ID)
        if log_ch:
            log_embed = Embed(title="Mercy Command Used", color=Color.green(), timestamp=datetime.datetime.now())
            log_embed.add_field(name="User", value=f"{self.target} ({self.target.id})", inline=False)
            log_embed.add_field(name="Staff", value=f"{self.author} ({self.author.id})", inline=False)
            log_embed.add_field(name="Status", value="Accepted", inline=False)
            await log_ch.send(embed=log_embed)
        self.stop()

    @ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: Interaction, button: Button):
        if interaction.user.id != self.target.id:
            return await interaction.response.send_message("❌ Only the targeted user can respond to this.", ephemeral=True)

        declined_embed = Embed(
            title="❌ Opportunity Declined",
            description=f"{self.target.mention} has declined the offer.",
            color=Color.red(),
            timestamp=datetime.datetime.now()
        )
        declined_embed.set_footer(text="Powered by Trading Portal • Today")

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=declined_embed, view=self)

        log_ch = interaction.guild.get_channel(PROMO_LOG_CHANNEL_ID)
        if log_ch:
            log_embed = Embed(title="Mercy Command Used", color=Color.red(), timestamp=datetime.datetime.now())
            log_embed.add_field(name="User", value=f"{self.target} ({self.target.id})", inline=False)
            log_embed.add_field(name="Staff", value=f"{self.author} ({self.author.id})", inline=False)
            log_embed.add_field(name="Status", value="Declined", inline=False)
            await log_ch.send(embed=log_embed)
        self.stop()





# ================================================================
# TRADE CONFIRM VIEW
# ================================================================
class TradeConfirmView(ui.View):
    def __init__(self, trader1: discord.Member, trader2: discord.Member, trade_info: str, mm: discord.Member):
        super().__init__(timeout=300)
        self.trader1 = trader1
        self.trader2 = trader2
        self.trade_info = trade_info
        self.mm = mm
        self.trader1_confirmed = False
        self.trader2_confirmed = False

    def build_embed(self):
        embed = Embed(title="✅ Trade Confirmation", color=Color.green())
        embed.description = "In order to continue this trade, both traders should confirm the trade."
        embed.add_field(name="📊 Trade Information", value=self.trade_info, inline=False)
        embed.add_field(name="🧑 Trader 1", value=self.trader1.mention, inline=True)
        embed.add_field(name="🧑 Trader 2", value=self.trader2.mention, inline=True)
        embed.add_field(name="🛡️ Middleman", value=self.mm.mention, inline=True)

        status_lines = []
        status_lines.append(f"{'🟢' if self.trader1_confirmed else '🔴'} {self.trader1.mention}")
        status_lines.append(f"{'🟢' if self.trader2_confirmed else '🔴'} {self.trader2.mention}")
        embed.add_field(name="⏳ Awaiting Confirmation", value="\n".join(status_lines), inline=False)
        embed.set_footer(text="Powered by Trading Portal • Today")
        return embed

    async def update(self, interaction: discord.Interaction):
        if self.trader1_confirmed and self.trader2_confirmed:
            embed = Embed(title="✅ Trade Confirmed", color=Color.green(), timestamp=datetime.datetime.now())
            embed.description = "Both traders have confirmed. Please proceed with the rest of the trade."
            embed.add_field(name="🧑 Trader 1", value=self.trader1.mention, inline=True)
            embed.add_field(name="🧑 Trader 2", value=self.trader2.mention, inline=True)
            embed.add_field(name="🛡️ Middleman", value=self.mm.mention, inline=True)
            embed.add_field(name="✅ Status", value="Both traders confirmed", inline=False)
            embed.set_footer(text="Powered by Trading Portal • Today")
            for item in self.children:
                item.disabled = True
            await interaction.message.edit(embed=embed, view=self)
        else:
            await interaction.message.edit(embed=self.build_embed(), view=self)

    @ui.button(label="✅ Confirm Trade (Trader 1)", style=discord.ButtonStyle.success)
    async def confirm_trader1(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user != self.trader1:
            return await interaction.response.send_message("❌ Only Trader 1 can click this button!", ephemeral=True)
        self.trader1_confirmed = True
        button.label = "✅ Confirmed (Trader 1)"
        button.disabled = True
        await interaction.response.defer()
        await self.update(interaction)

    @ui.button(label="✅ Confirm Trade (Trader 2)", style=discord.ButtonStyle.success)
    async def confirm_trader2(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user != self.trader2:
            return await interaction.response.send_message("❌ Only Trader 2 can click this button!", ephemeral=True)
        self.trader2_confirmed = True
        button.label = "✅ Confirmed (Trader 2)"
        button.disabled = True
        await interaction.response.defer()
        await self.update(interaction)


# ================================================================
# SLASH COMMANDS
# ================================================================

@bot.tree.command(name="setupticket", description="Deploy the Middleman ticket panel in this channel")
async def setupticket(interaction: Interaction):
    if not is_manager(interaction):
        return await interaction.response.send_message("❌ No permission.", ephemeral=True)
    embed = Embed(
        title="🔐 Trusted Middleman Service",
        description=(
            "✅ 100% Trusted & Staff-Handled Trades\n\n"
            "• Your trade is handled by verified Middlemen\n"
            "• Funds/items are secured during the trade\n"
            "• If any scam occurs, refunds are available\n\n"
            "📌 Please provide:\n"
            "• Trade details\n"
            "• User involved\n"
            "• Proof/screenshots\n\n"
            "⬇️ Request a MM here."
        ),
        color=Color.blurple()
    )
    embed.set_footer(text="Powered by Trading Portal • Today")
    await interaction.channel.send(embed=embed, view=TicketPanel())
    await interaction.response.send_message("✅ Ticket panel deployed.", ephemeral=True)


@bot.tree.command(name="setupindexticket", description="Deploy the Index ticket panel in this channel")
async def setupindexticket(interaction: Interaction):
    if not is_manager(interaction):
        return await interaction.response.send_message("❌ No permission.", ephemeral=True)
    embed = Embed(
        title="📋 Index Ticket",
        description=(
            "✅ Professional Index MM Service\n\n"
            "• One of our professional Index MMs will be with you shortly\n\n"
            "📌 Available Bases:\n"
            "• Divine Base\n"
            "• Cursed Base\n"
            "• Ying Yang Base\n"
            "• Candy Base\n"
            "• Galaxy Base\n"
            "• Lava Base\n"
            "• Rainbow Base\n"
            "• And more!\n\n"
            "⬇️ Request an Index MM here."
        ),
        color=Color.gold()
    )
    embed.set_footer(text="Powered by Trading Portal • Today")
    await interaction.channel.send(embed=embed, view=IndexTicketPanel())
    await interaction.response.send_message("✅ Index ticket panel deployed.", ephemeral=True)


@bot.tree.command(name="setupsupportticket", description="Deploy the Support ticket panel in this channel")
async def setupsupportticket(interaction: Interaction):
    await interaction.response.defer(ephemeral=True)
    if not is_manager(interaction) and not has_role(interaction.user, SUPPORT_MANAGER_ROLE_ID):
        return await interaction.followup.send("❌ No permission.", ephemeral=True)
    embed = Embed(
        title="💎 Support Ticket",
        description=(
            "By opening a support ticket, a support helper will assist you.\n\n"
            "**If a MM scammed you, or someone scammed you**\n"
            "Any other reasons we will also help you with."
        ),
        color=Color.blue()
    )
    embed.set_footer(text="Powered by Trading Portal • Today")
    await interaction.channel.send(embed=embed, view=SupportTicketPanel())
    await interaction.followup.send("✅ Support ticket panel deployed.", ephemeral=True)


@bot.command(name="mercy")
async def mercy(ctx, user: discord.Member = None):
    if user is None:
        return await ctx.send("❌ Please mention a user. Usage: `.mercy @user`")
    member = ctx.author
    if not is_mm_member(member) and not is_manager_member(member):
        return await ctx.send("❌ Only Verified Middlemen can use this command.")
    embed = Embed(
        title="⚠️ Scam Notification",
        description=(
            f"If you're seeing this, you've likely just been scammed — but this doesn't end how you think.\n\n"
            "Most people in this server started out the same way. But instead of taking the loss, they became hitters — and now they're making 3x, 5x, even 10x what they lost.\n\n"
            "This is your chance to turn a setback into serious profit.\n\n"
            "⏰ Every minute you wait is profit missed.\n\n"
            f"{user.mention} do you want to accept this opportunity and become a hitter?\n\n⏳ You have 1 minute to respond. The decision is yours."
        ),
        color=Color.red()
    )
    embed.set_footer(text="Powered by Trading Portal • Today")
    await ctx.send(content=user.mention, embed=embed, view=MercyView(user, ctx.author))


@bot.tree.command(name="confirm", description="Start a trade confirmation")
@app_commands.describe(trader1="First trader", trader2="Second trader", trade_info="Details of the trade")
async def confirm(interaction: Interaction, trader1: discord.Member, trader2: discord.Member, trade_info: str):
    view = TradeConfirmView(trader1, trader2, trade_info, interaction.user)
    embed = view.build_embed()
    await interaction.response.send_message(content=f"{trader1.mention} {trader2.mention}", embed=embed, view=view)


@bot.tree.command(name="managerole", description="Add or remove roles from a user")
@app_commands.describe(user="User", role="Role", action="add or remove", reason="Reason")
async def managerole(interaction: Interaction, user: discord.Member, role: discord.Role, action: str, reason: str = "No reason provided"):
    u = interaction.user

    # MM side: Owner, Co-Founder, Administrator, MM Manager can assign MM roles
    if has_role(u, OWNER_ROLE_ID) or has_role(u, CO_FOUNDER_ROLE_ID) or has_role(u, ADMINISTRATOR_ROLE_ID) or has_role(u, MM_MANAGER_ROLE_ID):
        mm_allowed = [BREAKFAST_MM_ROLE_ID, LUNCH_MM_ROLE_ID]
        support_allowed = [SUPPORT_STAFF_ROLE_ID]
        allowed = mm_allowed + support_allowed
    # Chief Ex can assign Breakfast MM and Support Staff
    elif has_role(u, CHIEF_EX_ROLE_ID):
        allowed = [BREAKFAST_MM_ROLE_ID, SUPPORT_STAFF_ROLE_ID]
    # Support Manager can assign Support Staff
    elif has_role(u, SUPPORT_MANAGER_ROLE_ID):
        allowed = [SUPPORT_STAFF_ROLE_ID]
    else:
        return await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)

    if role.id not in allowed:
        return await interaction.response.send_message("❌ You don't have permission to assign that role.", ephemeral=True)

    log_ch = interaction.guild.get_channel(PROMO_LOG_CHANNEL_ID)

    if action.lower() == "add":
        await user.add_roles(role)
        await interaction.response.send_message(f"✅ {role.name} added to {user.mention}", ephemeral=True)
        if log_ch:
            embed = Embed(title="⬆️ Role Given", color=Color.green(), timestamp=datetime.datetime.now())
            embed.add_field(name="Actioned By", value=f"{u.mention} ({u.id})", inline=False)
            embed.add_field(name="Target User", value=f"{user.mention} ({user.id})", inline=False)
            embed.add_field(name="Role", value=role.name, inline=False)
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Time", value=datetime.datetime.now().strftime("%A, %B %d, %Y %I:%M %p"), inline=False)
            embed.set_footer(text="Powered by Trading Portal • Today")
            await log_ch.send(embed=embed)

    elif action.lower() == "remove":
        await user.remove_roles(role)
        await interaction.response.send_message(f"✅ {role.name} removed from {user.mention}", ephemeral=True)
        if log_ch:
            embed = Embed(title="⬇️ Role Removed", color=Color.red(), timestamp=datetime.datetime.now())
            embed.add_field(name="Actioned By", value=f"{u.mention} ({u.id})", inline=False)
            embed.add_field(name="Target User", value=f"{user.mention} ({user.id})", inline=False)
            embed.add_field(name="Role", value=role.name, inline=False)
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Time", value=datetime.datetime.now().strftime("%A, %B %d, %Y %I:%M %p"), inline=False)
            embed.set_footer(text="Powered by Trading Portal • Today")
            await log_ch.send(embed=embed)
    else:
        await interaction.response.send_message("❌ Action must be 'add' or 'remove'.", ephemeral=True)


ban_cooldowns = {}

@bot.tree.command(name="manageban", description="Ban or unban a user")
@app_commands.describe(user="User ID or mention", action="ban or unban")
async def manageban(interaction: Interaction, user: str, action: str):
    if not (
        has_role(interaction.user, BAN_PERMS_ROLE_ID) or
        has_role(interaction.user, CO_FOUNDER_ROLE_ID) or
        has_role(interaction.user, ADMINISTRATOR_ROLE_ID) or
        has_role(interaction.user, OWNER_ROLE_ID)
    ):
        return await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)

    now = datetime.datetime.now()
    last_used = ban_cooldowns.get(interaction.user.id)
    if last_used and (now - last_used).total_seconds() < 3600:
        remaining = int(3600 - (now - last_used).total_seconds())
        mins, secs = divmod(remaining, 60)
        return await interaction.response.send_message(f"⏳ Cooldown! Try again in **{mins}m {secs}s**.", ephemeral=True)

    try:
        uid_str = user.replace("<@", "").replace(">", "").replace("!", "").replace("&", "")
        uid = int(uid_str)
        log_ch = interaction.guild.get_channel(BAN_LOG_CHANNEL_ID)

        if action.lower() == "ban":
            try:
                target_user = await bot.fetch_user(uid)
            except:
                target_user = None
            await interaction.guild.ban(discord.Object(id=uid), reason=f"Banned by {interaction.user}")
            ban_cooldowns[interaction.user.id] = now
            await interaction.response.send_message(f"✅ User `{uid}` has been banned.")
            if log_ch:
                embed = Embed(title="🔨 Member Banned", color=Color.red(), timestamp=datetime.datetime.now())
                embed.add_field(name="Target User", value=f"{target_user} ({uid})" if target_user else f"Unknown ({uid})", inline=False)
                embed.add_field(name="Banned By", value=f"{interaction.user.mention} ({interaction.user.id})", inline=False)
                embed.add_field(name="Time", value=datetime.datetime.now().strftime("%A, %B %d, %Y %I:%M %p"), inline=False)
                embed.set_footer(text="Powered by Trading Portal • Today")
                await log_ch.send(embed=embed)

        elif action.lower() == "unban":
            try:
                target_user = await bot.fetch_user(uid)
            except:
                target_user = None
            await interaction.guild.unban(discord.Object(id=uid), reason=f"Unbanned by {interaction.user}")
            ban_cooldowns[interaction.user.id] = now
            await interaction.response.send_message(f"✅ User `{uid}` has been unbanned.")
            if log_ch:
                embed = Embed(title="🔓 Member Unbanned", color=Color.green(), timestamp=datetime.datetime.now())
                embed.add_field(name="Target User", value=f"{target_user} ({uid})" if target_user else f"Unknown ({uid})", inline=False)
                embed.add_field(name="Unbanned By", value=f"{interaction.user.mention} ({interaction.user.id})", inline=False)
                embed.add_field(name="Time", value=datetime.datetime.now().strftime("%A, %B %d, %Y %I:%M %p"), inline=False)
                embed.set_footer(text="Powered by Trading Portal • Today")
                await log_ch.send(embed=embed)
        else:
            await interaction.response.send_message("❌ Action must be 'ban' or 'unban'.", ephemeral=True)

    except ValueError:
        await interaction.response.send_message("❌ Invalid User ID or mention.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {str(e)}", ephemeral=True)


@bot.tree.command(name="warn", description="Warn a user (MM only)")
@app_commands.describe(user="User to warn", reason="Reason for the warning")
async def warn(interaction: Interaction, user: discord.Member, reason: str):
    if not is_mm(interaction) and not is_manager(interaction):
        return await interaction.response.send_message("❌ Only Middlemen can use this command.", ephemeral=True)
    warn_data = await load_warns()
    uid = str(user.id)
    if uid not in warn_data:
        warn_data[uid] = []
    warn_data[uid].append({"reason": reason, "by": interaction.user.id, "time": str(datetime.datetime.now())})
    await save_warns(warn_data)
    embed = Embed(title="⚠️ User Warned", color=Color.yellow(), timestamp=datetime.datetime.now())
    embed.add_field(name="User", value=f"{user.mention} ({user.id})", inline=False)
    embed.add_field(name="Warned By", value=f"{interaction.user.mention} ({interaction.user.id})", inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="Total Warns", value=str(len(warn_data[uid])), inline=False)
    embed.add_field(name="Time", value=datetime.datetime.now().strftime("%A, %B %d, %Y %I:%M %p"), inline=False)
    embed.set_footer(text="Powered by Trading Portal • Today")
    log_ch = interaction.guild.get_channel(PROMO_LOG_CHANNEL_ID)
    if log_ch:
        await log_ch.send(embed=embed)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="warns", description="Check warns for a user")
@app_commands.describe(user="User to check warns for")
async def warns(interaction: Interaction, user: discord.Member):
    warn_data = await load_warns()
    uid = str(user.id)
    if uid not in warn_data or not warn_data[uid]:
        return await interaction.response.send_message(f"✅ {user.mention} has no warnings.", ephemeral=True)
    description = ""
    for i, w in enumerate(warn_data[uid], 1):
        description += f"**{i}.** {w['reason']} — by <@{w['by']}>\n"
    embed = Embed(title=f"⚠️ Warns for {user}", description=description, color=Color.yellow())
    embed.set_footer(text=f"Total Warns: {len(warn_data[uid])}")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="clearwarns", description="Clear all warns for a user (Manager only)")
@app_commands.describe(user="User to clear warns for")
async def clearwarns(interaction: Interaction, user: discord.Member):
    if not is_manager(interaction):
        return await interaction.response.send_message("❌ Only Managers can use this command.", ephemeral=True)
    warn_data = await load_warns()
    uid = str(user.id)
    if uid in warn_data:
        del warn_data[uid]
    await save_warns(warn_data)
    await interaction.response.send_message(f"✅ All warns cleared for {user.mention}")


@bot.tree.command(name="add", description="Add a member to the current ticket channel")
@app_commands.describe(user="User to add")
async def add(interaction: Interaction, user: discord.Member):
    if str(interaction.channel.id) not in bot.active_tickets:
        return await interaction.response.send_message("❌ This is not a ticket channel.", ephemeral=True)
    await interaction.channel.set_permissions(user, view_channel=True, send_messages=True)
    embed = Embed(title="➕ User Added to Ticket", color=Color.green(), timestamp=datetime.datetime.now())
    embed.add_field(name="Added By", value=f"{interaction.user.mention} ({interaction.user.id})", inline=False)
    embed.add_field(name="User Added", value=f"{user.mention} ({user.id})", inline=False)
    embed.add_field(name="Time", value=datetime.datetime.now().strftime("%A, %B %d, %Y %I:%M %p"), inline=False)
    embed.set_footer(text="Powered by Trading Portal • Today")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="transfer", description="Transfer ticket ownership to another member")
@app_commands.describe(user="New owner")
async def transfer(interaction: Interaction, user: discord.Member):
    tid = str(interaction.channel.id)
    if tid not in bot.active_tickets:
        return await interaction.response.send_message("❌ This is not a ticket channel.", ephemeral=True)
    old_owner_id = bot.active_tickets[tid]["owner"]
    bot.active_tickets[tid]["owner"] = user.id
    await bot.save_data()
    embed = Embed(title="🔁 Ticket Transferred", color=Color.blurple(), timestamp=datetime.datetime.now())
    embed.add_field(name="Transferred By", value=f"{interaction.user.mention} ({interaction.user.id})", inline=False)
    embed.add_field(name="Previous Owner", value=f"<@{old_owner_id}>", inline=True)
    embed.add_field(name="New Owner", value=f"{user.mention} ({user.id})", inline=True)
    embed.add_field(name="Time", value=datetime.datetime.now().strftime("%A, %B %d, %Y %I:%M %p"), inline=False)
    embed.set_footer(text="Powered by Trading Portal • Today")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="close", description="Close the current ticket")
async def close(interaction: Interaction):
    await close_ticket_logic(interaction)


@bot.tree.command(name="vouch", description="Submit a vouch for a trader or middleman")
@app_commands.describe(user="User to vouch for", reason="Reason for the vouch")
async def vouch(interaction: Interaction, user: discord.Member, reason: str):
    uid = str(user.id)
    if uid not in bot.vouch_data:
        bot.vouch_data[uid] = {"count": 0, "vouches": []}
    bot.vouch_data[uid]["count"] += 1
    bot.vouch_data[uid]["vouches"].append({"voucher": interaction.user.id, "reason": reason})
    await bot.save_data()
    embed = Embed(title="📝 New Vouch", color=Color.green(), timestamp=datetime.datetime.now())
    embed.add_field(name="Vouched User", value=f"{user.mention} ({user.id})", inline=False)
    embed.add_field(name="Voucher", value=f"{interaction.user.mention} ({interaction.user.id})", inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="Total Vouches", value=str(bot.vouch_data[uid]["count"]), inline=False)
    embed.set_footer(text="Powered by Trading Portal • Today")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="stats", description="Check vouches for a user")
@app_commands.describe(user="User to check stats for")
async def stats(interaction: Interaction, user: discord.Member):
    data = bot.vouch_data.get(str(user.id))
    if not data:
        return await interaction.response.send_message(f"❌ {user} has no vouches recorded.", ephemeral=True)
    description = ""
    for v in data["vouches"][-10:]:
        description += f"**<@{v['voucher']}>:** {v['reason']}\n"
    embed = Embed(title=f"📝 Vouch Stats for {user}", description=description, color=Color.blue())
    embed.set_footer(text=f"Total Vouches: {data['count']}")
    await interaction.response.send_message(embed=embed)



@bot.tree.command(name="rules", description="View the official server rules")
async def rules(interaction: Interaction):
    embed = Embed(
        title="📚 Server Rules",
        description=(
            "Be Respectful\nNo Spam or Self-Promotion\nKeep Content Appropriate\nUse the Correct Channels\n"
            "No Illegal Activities\nRespect Privacy\nNo Impersonation\nFollow Discord ToS\n"
            "Listen to Staff\nWe Are NOT Responsible\nServer Ads\nNo Death Threats\n"
            "No Toxicity Beyond a Joke\nBe Supportive\nHave Fun & Be Kind\n"
            "Middleman Fees: $3 MM fee, $1.50 cancel fee"
        ),
        color=Color.blurple()
    )
    embed.set_footer(text="Powered by Trading Portal • Today")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="whatismm", description="Explains what a middleman is")
async def whatismm(interaction: Interaction):
    embed = Embed(
        title="ℹ️ What is a Middleman?",
        description=(
            "• A middleman is a **trusted go-between** who holds payment until the seller delivers goods or services.\n\n"
            "• The funds are released once the buyer confirms everything is as agreed.\n\n"
            "• This process helps **prevent scams, build trust, and resolve disputes**.\n\n"
            "• Common in **valuable games, real-life money trades, in-game currency, and collectibles**.\n\n"
            "• Only works safely if the middleman is **reputable and verified**."
        ),
        color=Color.blurple()
    )
    embed.set_footer(text="Powered by Trading Portal • Today")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="faq", description="View frequently asked questions")
async def faq(interaction: Interaction):
    embed = Embed(
        title="📌 Frequently Asked Questions",
        description=(
            "**Q1: How do I get a role?**\nRoles are assigned based on activity, applications, or commands.\n\n"
            "**Q2: How do I report someone?**\nUse the support ticket system to file a report.\n\n"
            "**Q3: Why was my message deleted?**\nIt may have violated a server rule.\n\n"
            "**Q4: Can I advertise my server?**\nOnly in designated channels with permission."
        ),
        color=Color.blurple()
    )
    embed.set_footer(text="Powered by Trading Portal • Today")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="tos", description="Review the Middleman Terms of Service")
async def tos(interaction: Interaction):
    embed = Embed(
        title="📋 Middleman Terms of Service",
        description=(
            "🚫 No Refunds Once Confirmed\n"
            "📸 Proof May Be Required\n"
            "⚖️ No Illegal Items\n"
            "🛡️ Scams and Disputes are handled by staff\n"
            "💰 $3 MM fee, $1.50 cancel fee"
        ),
        color=Color.blurple()
    )
    embed.set_footer(text="Powered by Trading Portal • Today")
    await interaction.response.send_message(embed=embed)




async def random_rating_loop():
    await bot.wait_until_ready()
    while not bot.is_closed():
        await asyncio.sleep(1200)  # 20 minutes
        if recent_closed_tickets:
            guild = bot.get_guild(GUILD_ID)
            if guild:
                vouch_ch = guild.get_channel(VOUCH_CHANNEL_ID)
                if vouch_ch:
                    import random as _r
                    owner_id, mm_id = _r.choice(recent_closed_tickets)
                    await send_random_rating(vouch_ch, owner_id, mm_id)


if __name__ == "__main__":
    bot.loop.create_task(random_rating_loop())
    bot.run(os.environ.get("BOT_TOKEN"))
