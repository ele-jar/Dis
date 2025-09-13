import discord
from discord.ext import commands
from discord import app_commands, ui, Member, Role
from typing import Union
import os
import sqlite3
from .ticket_system import generate_transcript_file

async def is_support_staff(interaction: discord.Interaction) -> bool:
    with sqlite3.connect(interaction.client.db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM tickets WHERE channel_id = ?", (interaction.channel.id,))
        if not cursor.fetchone():
            await interaction.response.send_message("This command can only be used in a ticket channel.", ephemeral=True, delete_after=10)
            return False
            
        # UPDATED: Select support_role_ids
        cursor.execute("SELECT p.support_role_ids FROM panels p JOIN tickets t ON p.panel_id = t.panel_id WHERE t.channel_id = ?", (interaction.channel.id,))
        role_ids_tuple = cursor.fetchone()
        if not role_ids_tuple: return False
    
    # NEW: Logic to check multiple roles
    support_role_ids = {int(r_id) for r_id in role_ids_tuple[0].split(',') if r_id}
    user_role_ids = {role.id for role in interaction.user.roles}

    if not (user_role_ids.intersection(support_role_ids) or interaction.user.guild_permissions.administrator):
        await interaction.response.send_message("You do not have the required support role to use this command.", ephemeral=True)
        return False
    return True

class TicketCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def execute_close(self, interaction: discord.Interaction, closed_by: discord.Member):
        with sqlite3.connect(self.bot.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT t.*, p.transcript_channel_id FROM tickets t JOIN panels p ON t.panel_id = p.panel_id WHERE t.channel_id = ? AND t.status = 'open'", (interaction.channel.id,))
            ticket = cursor.fetchone()
            if not ticket:
                if interaction.response.is_done():
                    await interaction.followup.send("This is not an open ticket.", ephemeral=True)
                else:
                    await interaction.response.send_message("This is not an open ticket.", ephemeral=True)
                return

            cursor.execute("UPDATE tickets SET status = 'closed' WHERE channel_id = ?", (interaction.channel.id,))
            conn.commit()

        await interaction.channel.edit(name=f"closed-{ticket['ticket_num']:04d}")
        owner = interaction.guild.get_member(ticket['owner_id'])
        if owner: await interaction.channel.set_permissions(owner, send_messages=False, read_messages=True)

        embed = discord.Embed(title="Ticket Closed", description=f"Ticket closed by {closed_by.mention}.", color=discord.Color.red())
        transcript_filename = await generate_transcript_file(interaction.channel)
        
        if (trans_channel := interaction.guild.get_channel(ticket['transcript_channel_id'])):
            owner_mention = owner.mention if owner else f"ID: {ticket['owner_id']}"
            await trans_channel.send(f"Transcript for ticket `#{ticket['ticket_num']}` created by {owner_mention}", file=discord.File(transcript_filename))
        os.remove(transcript_filename)
        
        if interaction.message:
            await interaction.message.edit(content=None, embed=embed, view=self.bot.get_cog('TicketSystem').ClosedTicketView())
        else:
            await interaction.channel.send(embed=embed, view=self.bot.get_cog('TicketSystem').ClosedTicketView())

    async def execute_open(self, interaction: discord.Interaction):
        with sqlite3.connect(self.bot.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tickets WHERE channel_id = ? AND status = 'closed'", (interaction.channel.id,))
            ticket = cursor.fetchone()
            if not ticket:
                await interaction.followup.send("This is not a closed ticket.", ephemeral=True)
                return

            cursor.execute("UPDATE tickets SET status = 'open' WHERE channel_id = ?", (interaction.channel.id,))
            conn.commit()
        
        await interaction.channel.edit(name=f"ticket-{ticket['ticket_num']:04d}")
        if (owner := interaction.guild.get_member(ticket['owner_id'])):
            await interaction.channel.set_permissions(owner, send_messages=True, read_messages=True)
        
        embed = discord.Embed(title="Ticket Re-Opened", description=f"Ticket re-opened by {interaction.user.mention}.", color=discord.Color.green())
        await interaction.message.edit(content=None, embed=embed, view=self.bot.get_cog('TicketSystem').OpenTicketView())

    @app_commands.command(name="add")
    @app_commands.check(is_support_staff)
    async def add(self, interaction: discord.Interaction, target: Union[Member, Role]):
        await interaction.channel.set_permissions(target, read_messages=True, send_messages=True)
        await interaction.response.send_message(f"{target.mention} has been added to this ticket.")

    @app_commands.command(name="remove")
    @app_commands.check(is_support_staff)
    async def remove(self, interaction: discord.Interaction, target: Union[Member, Role]):
        await interaction.channel.set_permissions(target, overwrite=None)
        await interaction.response.send_message(f"{target.mention} has been removed from this ticket.")

    @app_commands.command(name="close")
    @app_commands.check(is_support_staff)
    async def close(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.execute_close(interaction, interaction.user)
        await interaction.followup.send("Close command executed.", ephemeral=True)

    @app_commands.command(name="open")
    @app_commands.check(is_support_staff)
    async def open(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.execute_open(interaction)

    @app_commands.command(name="rename")
    @app_commands.check(is_support_staff)
    async def rename(self, interaction: discord.Interaction, name: str):
        await interaction.channel.edit(name=name)
        await interaction.response.send_message(f"Ticket has been renamed to `{name}`.")

    @app_commands.command(name="transcript")
    @app_commands.check(is_support_staff)
    async def transcript(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        filename = await generate_transcript_file(interaction.channel)
        await interaction.followup.send(file=discord.File(filename), ephemeral=True)
        os.remove(filename)

    @app_commands.command(name="claim")
    @app_commands.check(is_support_staff)
    async def claim(self, interaction: discord.Interaction):
        with sqlite3.connect(self.bot.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT t.claimed_by_id, p.is_claimable FROM tickets t JOIN panels p ON t.panel_id = p.panel_id WHERE t.channel_id = ?", (interaction.channel.id,))
            claimed_by_id, is_claimable = cursor.fetchone()
            
            if not is_claimable:
                return await interaction.response.send_message("This ticket panel does not support claiming.", ephemeral=True)
            
            if claimed_by_id is None:
                cursor.execute("UPDATE tickets SET claimed_by_id = ? WHERE channel_id = ?", (interaction.user.id, interaction.channel.id))
                await interaction.response.send_message(embed=discord.Embed(description=f"Ticket claimed by {interaction.user.mention}", color=discord.Color.gold()))
            elif claimed_by_id == interaction.user.id:
                cursor.execute("UPDATE tickets SET claimed_by_id = NULL WHERE channel_id = ?", (interaction.channel.id,))
                await interaction.response.send_message(embed=discord.Embed(description=f"Ticket has been unclaimed by {interaction.user.mention}", color=discord.Color.light_grey()))
            else:
                claimer = interaction.guild.get_member(claimed_by_id)
                await interaction.response.send_message(f"This ticket is already claimed by {claimer.mention if claimer else 'an unknown user'}.", ephemeral=True)
            conn.commit()
    
    @app_commands.command(name="closerequest")
    @app_commands.check(is_support_staff)
    async def closerequest(self, interaction: discord.Interaction):
        with sqlite3.connect(self.bot.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT owner_id FROM tickets WHERE channel_id = ?", (interaction.channel.id,))
            owner_id_tuple = cursor.fetchone()
        
        owner = interaction.guild.get_member(owner_id_tuple[0]) if owner_id_tuple else None
        embed = discord.Embed(title="Close Request", description=f"Hi {owner.mention if owner else 'there'}, our support staff believes this issue has been resolved. If you agree, a staff member will press the button below to close this ticket.", color=discord.Color.blurple())
        await interaction.response.send_message(embed=embed, view=self.bot.get_cog('TicketSystem').CloseRequestView())

async def setup(bot: commands.Bot):
    await bot.add_cog(TicketCommands(bot))
