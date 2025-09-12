import discord
from discord.ext import commands
from discord import app_commands, ui, Member, Role
from typing import Union
import os
from .ticket_system import generate_transcript_file

async def is_ticket_channel(interaction: discord.Interaction) -> bool:
    conn, cursor = interaction.client.get_db_connection()
    cursor.execute("SELECT 1 FROM tickets WHERE channel_id = ?", (interaction.channel.id,))
    return cursor.fetchone() is not None

async def is_support_staff(interaction: discord.Interaction) -> bool:
    conn, cursor = interaction.client.get_db_connection()
    cursor.execute("SELECT 1 FROM tickets WHERE channel_id = ?", (interaction.channel.id,))
    if not cursor.fetchone():
        await interaction.response.send_message("This command can only be used in a ticket channel.", ephemeral=True, delete_after=10)
        return False
        
    cursor.execute("SELECT p.support_role_id FROM panels p JOIN tickets t ON p.panel_id = t.panel_id WHERE t.channel_id = ?", (interaction.channel.id,))
    role_id = cursor.fetchone()
    if not role_id: return False
    
    support_role = interaction.guild.get_role(role_id[0])
    if not (support_role in interaction.user.roles or interaction.user.guild_permissions.administrator):
        await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
        return False
    return True

class TicketCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def execute_close(self, interaction: discord.Interaction, closed_by: discord.Member):
        conn, cursor = self.bot.get_db_connection()
        cursor.execute("SELECT t.*, p.transcript_channel_id FROM tickets t JOIN panels p ON t.panel_id = p.panel_id WHERE t.channel_id = ? AND t.status = 'open'", (interaction.channel.id,))
        ticket = cursor.fetchone()
        if not ticket:
            await interaction.followup.send("This is not an open ticket.", ephemeral=True)
            return

        _, _, _, _, owner_id, _, ticket_num, _, trans_channel_id = ticket
        cursor.execute("UPDATE tickets SET status = 'closed' WHERE channel_id = ?", (interaction.channel.id,))
        conn.commit()

        await interaction.channel.edit(name=f"closed-{ticket_num:04d}")
        owner = interaction.guild.get_member(owner_id)
        if owner: await interaction.channel.set_permissions(owner, send_messages=False, read_messages=True)

        embed = discord.Embed(title="Ticket Closed", description=f"Ticket closed by {closed_by.mention}.", color=discord.Color.red())
        transcript_filename = await generate_transcript_file(interaction.channel)
        
        if (trans_channel := interaction.guild.get_channel(trans_channel_id)):
            await trans_channel.send(f"Transcript for ticket `#{ticket_num}` created by {owner.mention if owner else 'Unknown User'}", file=discord.File(transcript_filename))
        os.remove(transcript_filename)
        
        # BUG FIX: Edit the existing message instead of sending a new one.
        await interaction.message.edit(content=None, embed=embed, view=self.bot.get_cog('TicketSystem').ClosedTicketView())


    async def execute_open(self, interaction: discord.Interaction):
        conn, cursor = self.bot.get_db_connection()
        cursor.execute("SELECT * FROM tickets WHERE channel_id = ? AND status = 'closed'", (interaction.channel.id,))
        ticket = cursor.fetchone()
        if not ticket: return await interaction.followup.send("This is not a closed ticket.", ephemeral=True)

        _, _, _, _, owner_id, _, ticket_num, _ = ticket
        cursor.execute("UPDATE tickets SET status = 'open' WHERE channel_id = ?", (interaction.channel.id,))
        conn.commit()
        
        await interaction.channel.edit(name=f"ticket-{ticket_num:04d}")
        if (owner := interaction.guild.get_member(owner_id)):
            await interaction.channel.set_permissions(owner, send_messages=True, read_messages=True)
        
        embed = discord.Embed(title="Ticket Re-Opened", description=f"Ticket re-opened by {interaction.user.mention}.", color=discord.Color.green())

        # BUG FIX: Edit the existing message instead of sending a new one.
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
    @app_commands.check(is_ticket_channel)
    async def close(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.execute_close(interaction, interaction.user)

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
        conn, cursor = self.bot.get_db_connection()
        cursor.execute("SELECT t.claimed_by_id, p.is_claimable FROM tickets t JOIN panels p ON t.panel_id = p.panel_id WHERE t.channel_id = ?", (interaction.channel.id,))
        claimed_by_id, is_claimable = cursor.fetchone()
        
        if not is_claimable: return await interaction.response.send_message("This ticket panel does not support claiming.", ephemeral=True)
        
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
        conn, cursor = self.bot.get_db_connection()
        cursor.execute("SELECT owner_id FROM tickets WHERE channel_id = ?", (interaction.channel.id,))
        owner = interaction.guild.get_member(cursor.fetchone()[0])
        embed = discord.Embed(title="Close Request", description=f"Hi {owner.mention if owner else 'there'}, has your issue been resolved? If so, you may close this ticket by pressing the button below.", color=discord.Color.blurple())
        await interaction.response.send_message(embed=embed, view=self.bot.get_cog('TicketSystem').CloseRequestView())

async def setup(bot: commands.Bot):
    await bot.add_cog(TicketCommands(bot))
