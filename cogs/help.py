import discord
from discord.ext import commands
from discord import app_commands

class HelpCommand(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Shows the list of ticket tool commands.")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Ticket Tool Ticket Commands",
            color=discord.Color.blurple()
        )
        embed.add_field(name="/add `target`", value="Gives a user or role access to the current ticket channel.", inline=False)
        embed.add_field(name="/remove `target`", value="Removes a user or role's access to the ticket channel.", inline=False)
        embed.add_field(name="/open", value="Re-opens a ticket channel that is in the Closed state.", inline=False)
        embed.add_field(name="/close", value="Closes a ticket channel that is in the Opened state.", inline=False)
        embed.add_field(name="/rename `name`", value="Changes the ticket name.", inline=False)
        embed.add_field(name="/claim", value="Allows a support team member to claim or unclaim the ticket.", inline=False)
        embed.add_field(name="/closerequest", value="Sends a Close Ask Message to the ticket channel.", inline=False)
        embed.add_field(name="/transcript", value="Generates a transcript of the ticket.", inline=False)
        embed.set_footer(text="Use /setup to create a new ticket panel.")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCommand(bot))
