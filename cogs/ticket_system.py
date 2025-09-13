import discord
from discord.ext import commands
from discord import ui
import aiofiles
import os
import datetime
import asyncio
import sqlite3
import html

async def generate_transcript_file(channel: discord.TextChannel):
    # **NEW**: Comprehensive CSS for responsive design and better visuals
    css = """
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #36393f; color: #dcddde; margin: 0; padding: 20px; }
        .container { max-width: 800px; margin: auto; }
        .header { text-align: center; border-bottom: 1px solid #4f545c; padding-bottom: 10px; margin-bottom: 20px; }
        .header h1 { color: #ffffff; }
        .message-group { display: flex; margin-bottom: 20px; }
        .avatar { width: 40px; height: 40px; border-radius: 50%; margin-right: 15px; flex-shrink: 0; }
        .message-content { display: flex; flex-direction: column; width: 100%; }
        .author-info { display: flex; align-items: center; margin-bottom: 5px; }
        .author-name { font-weight: bold; color: #ffffff; }
        .timestamp { color: #72767d; font-size: 0.75em; margin-left: 10px; }
        .content { white-space: pre-wrap; word-wrap: break-word; }
        .embed { border-left: 4px solid #4f545c; background-color: #2f3136; padding: 10px; border-radius: 4px; margin-top: 5px; }
        .embed-title { font-weight: bold; }
        .embed-description { font-size: 0.9em; }
        .embed-field { margin-top: 5px; }
        .embed-field-name { font-weight: bold; }
        .attachment img { max-width: 100%; height: auto; border-radius: 4px; margin-top: 5px; }
        .attachment a { color: #00a8fc; }
    </style>
    """
    
    html_content = f"<!DOCTYPE html><html><head><title>Transcript for #{channel.name}</title>{css}</head><body><div class='container'>"
    html_content += f"<div class='header'><h1>Transcript for #{channel.name}</h1></div>"
    
    async for message in channel.history(limit=None, oldest_first=True):
        timestamp = message.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')
        safe_content = html.escape(message.clean_content)

        html_content += f'<div class="message-group">'
        html_content += f'<img src="{message.author.display_avatar.url}" class="avatar">'
        html_content += '<div class="message-content">'
        html_content += f'<div class="author-info"><span class="author-name">{html.escape(message.author.display_name)}</span> <span class="timestamp">{timestamp}</span></div>'
        if safe_content:
            html_content += f'<div class="content">{safe_content}</div>'
        
        # **NEW**: Handle attachments
        if message.attachments:
            for attachment in message.attachments:
                if attachment.content_type and attachment.content_type.startswith('image/'):
                    html_content += f'<div class="attachment"><a href="{attachment.url}" target="_blank"><img src="{attachment.url}" alt="Attachment"></a></div>'
                else:
                    html_content += f'<div class="attachment"><a href="{attachment.url}" target="_blank">{html.escape(attachment.filename)}</a></div>'

        # **NEW**: Handle embeds
        if message.embeds:
            for embed in message.embeds:
                html_content += '<div class="embed">'
                if embed.title:
                    html_content += f'<div class="embed-title">{html.escape(embed.title)}</div>'
                if embed.description:
                    html_content += f'<div class="embed-description">{html.escape(embed.description)}</div>'
                if embed.fields:
                    for field in embed.fields:
                        html_content += '<div class="embed-field">'
                        html_content += f'<div class="embed-field-name">{html.escape(field.name)}</div>'
                        html_content += f'<div class="embed-field-value">{html.escape(field.value)}</div>'
                        html_content += '</div>'
                html_content += '</div>'
        
        html_content += '</div></div>'

    html_content += "</div></body></html>"
    
    filename = f"transcript-{channel.name}.html"
    async with aiofiles.open(filename, 'w', encoding='utf-8') as f:
        await f.write(html_content)
    return filename

class TicketSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _is_support_staff(self, interaction: discord.Interaction) -> bool:
        with sqlite3.connect(self.bot.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT p.support_role_id FROM panels p JOIN tickets t ON p.panel_id = t.panel_id WHERE t.channel_id = ?", (interaction.channel.id,))
            role_id_tuple = cursor.fetchone()
        
        if not role_id_tuple:
            await interaction.response.send_message("Error: Could not find panel configuration for this ticket.", ephemeral=True)
            return False
            
        support_role = interaction.guild.get_role(role_id_tuple[0])
        if not support_role:
             await interaction.response.send_message("Error: Support role not found.", ephemeral=True)
             return False

        if not (support_role in interaction.user.roles or interaction.user.guild_permissions.administrator):
            await interaction.response.send_message("You do not have the required support role for this action.", ephemeral=True)
            return False
        return True

    class CreateTicketView(ui.View):
        def __init__(self): super().__init__(timeout=None)
        
        @ui.button(label="Create Ticket", style=discord.ButtonStyle.primary, custom_id="persistent:create_ticket")
        async def create_ticket(self, interaction: discord.Interaction, button: ui.Button):
            await interaction.response.defer(ephemeral=True, thinking=True)
            
            with sqlite3.connect(interaction.client.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM panels WHERE message_id = ?", (interaction.message.id,))
                panel = cursor.fetchone()
                if not panel: return await interaction.followup.send("This ticket panel is outdated or misconfigured.", ephemeral=True)
                
                cursor.execute("SELECT 1 FROM tickets WHERE owner_id = ? AND status = 'open' AND panel_id = ?", (interaction.user.id, panel['panel_id']))
                if cursor.fetchone(): return await interaction.followup.send("You already have an open ticket from this panel.", ephemeral=True)

                guild, support_role, category = interaction.guild, interaction.guild.get_role(panel['support_role_id']), interaction.guild.get_channel(panel['category_id'])
                if not support_role or not category: return await interaction.followup.send("Configuration error: Support role or category not found.", ephemeral=True)

                cursor.execute("INSERT INTO tickets (guild_id, panel_id, channel_id, owner_id, status, ticket_num) VALUES (?, ?, ?, ?, ?, ?)", (guild.id, panel['panel_id'], 0, interaction.user.id, 'open', 0))
                ticket_id = cursor.lastrowid
                ticket_num = ticket_id
                cursor.execute("UPDATE tickets SET ticket_num = ? WHERE ticket_id = ?", (ticket_num, ticket_id))
                conn.commit()
            
            overwrites = { guild.default_role: discord.PermissionOverwrite(read_messages=False), interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True), support_role: discord.PermissionOverwrite(read_messages=True, send_messages=True), guild.me: discord.PermissionOverwrite(read_messages=True) }
            
            try: channel = await category.create_text_channel(name=f"ticket-{ticket_num:04d}", overwrites=overwrites)
            except discord.Forbidden:
                with sqlite3.connect(interaction.client.db_path) as conn:
                    conn.cursor().execute("DELETE FROM tickets WHERE ticket_id = ?", (ticket_id,))
                return await interaction.followup.send("I lack permissions to create channels in the ticket category.", ephemeral=True)

            with sqlite3.connect(interaction.client.db_path) as conn:
                conn.cursor().execute("UPDATE tickets SET channel_id = ? WHERE ticket_id = ?", (channel.id, ticket_id))
                conn.commit()
            
            embed = discord.Embed(title="Welcome to your ticket!", description=panel['welcome_message'], color=discord.Color.dark_green())
            await channel.send(f"{interaction.user.mention} {support_role.mention}", embed=embed, view=interaction.client.get_cog('TicketSystem').OpenTicketView())
            await interaction.followup.send(f"Your ticket has been created: {channel.mention}", ephemeral=True)

    class OpenTicketView(ui.View):
        def __init__(self): super().__init__(timeout=None)
        
        @ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="persistent:close_ticket")
        async def close_ticket(self, interaction: discord.Interaction, button: ui.Button):
            if not await interaction.client.get_cog("TicketSystem")._is_support_staff(interaction):
                return
            await interaction.response.defer()
            await interaction.client.get_cog("TicketCommands").execute_close(interaction, interaction.user)
    
    class ClosedTicketView(ui.View):
        def __init__(self): super().__init__(timeout=None)
        
        @ui.button(label="Re-Open", style=discord.ButtonStyle.success, emoji="🔓", custom_id="persistent:reopen_ticket")
        async def reopen_ticket(self, interaction: discord.Interaction, button: ui.Button):
            if not await interaction.client.get_cog("TicketSystem")._is_support_staff(interaction):
                return
            await interaction.response.defer()
            await interaction.client.get_cog("TicketCommands").execute_open(interaction)

        @ui.button(label="Delete", style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="persistent:delete_ticket")
        async def delete_ticket(self, interaction: discord.Interaction, button: ui.Button):
            if not await interaction.client.get_cog("TicketSystem")._is_support_staff(interaction):
                return
                
            await interaction.response.send_message("Channel will be deleted in 5 seconds.", ephemeral=True)
            await asyncio.sleep(5)
            with sqlite3.connect(interaction.client.db_path) as conn:
                conn.cursor().execute("DELETE FROM tickets WHERE channel_id = ?", (interaction.channel.id,))
                conn.commit()
            await interaction.channel.delete()

    class CloseRequestView(ui.View):
        def __init__(self): super().__init__(timeout=None)
        
        @ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="persistent:confirm_close_ticket")
        async def confirm_close(self, interaction: discord.Interaction, button: ui.Button):
            if not await interaction.client.get_cog("TicketSystem")._is_support_staff(interaction):
                return
            
            await interaction.response.defer()
            await interaction.client.get_cog("TicketCommands").execute_close(interaction, interaction.user)

async def setup(bot: commands.Bot):
    await bot.add_cog(TicketSystem(bot))
