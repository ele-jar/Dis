import discord
from discord.ext import commands
from discord import ui
import aiofiles
import os
import datetime
import asyncio

async def generate_transcript_file(channel: discord.TextChannel):
    html_content = (
        "<!DOCTYPE html><html><head><title>Transcript</title><style>"
        "body { font-family: sans-serif; background-color: #36393f; color: #dcddde; }"
        ".message { display: flex; align-items: flex-start; margin-bottom: 15px; }"
        ".avatar { width: 40px; height: 40px; border-radius: 50%; margin-right: 15px; }"
        ".message-content { display: flex; flex-direction: column; }"
        ".author { font-weight: bold; margin-bottom: 3px; }"
        ".timestamp { color: #72767d; font-size: 0.75em; }"
        ".content { white-space: pre-wrap; }"
        "</style></head><body>"
        f"<h1>Transcript for #{channel.name}</h1>"
    )
    
    async for message in channel.history(limit=None, oldest_first=True):
        timestamp = message.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')
        html_content += (
            f'<div class="message">'
            f'<img src="{message.author.display_avatar.url}" class="avatar">'
            f'<div class="message-content">'
            f'<div><span class="author">{message.author.display_name}</span> <span class="timestamp">{timestamp}</span></div>'
            f'<div class="content">{message.clean_content}</div>'
            f'</div></div>'
        )
    html_content += "</body></html>"
    
    filename = f"transcript-{channel.name}.html"
    async with aiofiles.open(filename, 'w', encoding='utf-8') as f:
        await f.write(html_content)
    return filename

class TicketSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    class CreateTicketView(ui.View):
        def __init__(self): super().__init__(timeout=None)
        
        @ui.button(label="Create Ticket", style=discord.ButtonStyle.primary, custom_id="persistent:create_ticket")
        async def create_ticket(self, interaction: discord.Interaction, button: ui.Button):
            await interaction.response.defer(ephemeral=True, thinking=True)
            
            conn, cursor = interaction.client.get_db_connection()
            # Fetch the new custom text columns from the database
            cursor.execute("SELECT panel_id, support_role_id, category_id, welcome_message FROM panels WHERE message_id = ?", (interaction.message.id,))
            panel_data = cursor.fetchone()
            if not panel_data: return await interaction.followup.send("This ticket panel is outdated.", ephemeral=True)
            
            panel_id, role_id, cat_id, welcome_message = panel_data
            
            cursor.execute("SELECT * FROM tickets WHERE owner_id = ? AND status = 'open' AND panel_id = ?", (interaction.user.id, panel_id))
            if cursor.fetchone(): return await interaction.followup.send("You already have an open ticket from this panel.", ephemeral=True)

            guild, support_role, category = interaction.guild, interaction.guild.get_role(role_id), interaction.guild.get_channel(cat_id)
            if not support_role or not category: return await interaction.followup.send("Configuration error: Support role or category not found.", ephemeral=True)

            cursor.execute("INSERT INTO tickets (guild_id, panel_id, channel_id, owner_id, status, ticket_num) VALUES (?, ?, ?, ?, ?, ?)", (guild.id, panel_id, 0, interaction.user.id, 'open', 0))
            ticket_id = cursor.lastrowid
            conn.commit()
            ticket_num = ticket_id
            
            overwrites = { guild.default_role: discord.PermissionOverwrite(read_messages=False), interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True), support_role: discord.PermissionOverwrite(read_messages=True, send_messages=True), guild.me: discord.PermissionOverwrite(read_messages=True) }
            
            try: channel = await category.create_text_channel(name=f"ticket-{ticket_num:04d}", overwrites=overwrites)
            except discord.Forbidden:
                cursor.execute("DELETE FROM tickets WHERE ticket_id = ?", (ticket_id,))
                conn.commit()
                return await interaction.followup.send("I lack permissions to create channels in the ticket category.", ephemeral=True)

            cursor.execute("UPDATE tickets SET channel_id = ?, ticket_num = ? WHERE ticket_id = ?", (channel.id, ticket_num, ticket_id))
            conn.commit()
            
            embed = discord.Embed(title="Welcome to your ticket!", description=welcome_message, color=discord.Color.dark_green())
            await channel.send(f"{interaction.user.mention} {support_role.mention}", embed=embed, view=interaction.client.get_cog('TicketSystem').OpenTicketView())
            await interaction.followup.send(f"Your ticket has been created: {channel.mention}", ephemeral=True)

    class OpenTicketView(ui.View):
        def __init__(self): super().__init__(timeout=None)
        
        @ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="persistent:close_ticket")
        async def close_ticket(self, interaction: discord.Interaction, button: ui.Button):
            conn, cursor = interaction.client.get_db_connection()
            cursor.execute("SELECT p.support_role_id FROM tickets t JOIN panels p ON t.panel_id = p.panel_id WHERE t.channel_id = ?", (interaction.channel.id,))
            result = cursor.fetchone()
            if not result: return
            
            support_role_id = result[0]
            support_role = interaction.guild.get_role(support_role_id)

            # **THE FIX IS HERE: This check now ONLY allows staff or admins to close the ticket.**
            if not (support_role in interaction.user.roles or interaction.user.guild_permissions.administrator):
                return await interaction.response.send_message("Only staff members can close this ticket.", ephemeral=True)

            await interaction.response.defer()
            await interaction.client.get_cog("TicketCommands").execute_close(interaction, interaction.user)
    
    class ClosedTicketView(ui.View):
        def __init__(self): super().__init__(timeout=None)
        
        @ui.button(label="Re-Open", style=discord.ButtonStyle.success, emoji="🔓", custom_id="persistent:reopen_ticket")
        async def reopen_ticket(self, interaction: discord.Interaction, button: ui.Button):
            await interaction.response.defer()
            await interaction.client.get_cog("TicketCommands").execute_open(interaction)

        @ui.button(label="Delete", style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="persistent:delete_ticket")
        async def delete_ticket(self, interaction: discord.Interaction, button: ui.Button):
            await interaction.response.send_message("Channel will be deleted in 5 seconds.", ephemeral=True)
            await asyncio.sleep(5)
            conn, cursor = interaction.client.get_db_connection()
            cursor.execute("DELETE FROM tickets WHERE channel_id = ?", (interaction.channel.id,))
            conn.commit()
            await interaction.channel.delete()

    class CloseRequestView(ui.View):
        def __init__(self): super().__init__(timeout=None)
        
        @ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="persistent:confirm_close_ticket")
        async def confirm_close(self, interaction: discord.Interaction, button: ui.Button):
            conn, cursor = interaction.client.get_db_connection()
            cursor.execute("SELECT owner_id FROM tickets WHERE channel_id = ?", (interaction.channel.id,))
            owner_id = cursor.fetchone()
            if not owner_id or interaction.user.id != owner_id[0]:
                return await interaction.response.send_message("Only the ticket owner can use this button.", ephemeral=True)
            
            await interaction.response.defer()
            await interaction.client.get_cog("TicketCommands").execute_close(interaction, interaction.user)

async def setup(bot: commands.Bot):
    await bot.add_cog(TicketSystem(bot))
