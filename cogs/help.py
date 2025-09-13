import discord
from discord.ext import commands
from discord import app_commands

class HelpCommand(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Shows the list of ticket tool commands.")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Ticket Tool Commands",
            color=discord.Color.blurple()
        )
        embed.add_field(name="/setup", value="Guides you through creating a new ticket panel.", inline=False)
        embed.add_field(name="/editpanel", value="Allows you to edit an existing ticket panel.", inline=False)
        embed.add_field(name="Ticket Management Commands", value="These can only be used inside a ticket channel.", inline=False)
        embed.add_field(name="/add `target`", value="Gives a user or role access to the current ticket channel.", inline=True)
        embed.add_field(name="/remove `target`", value="Removes a user or role's access to the ticket channel.", inline=True)
        embed.add_field(name="/open", value="Re-opens a ticket channel.", inline=True)
        embed.add_field(name="/close", value="Closes the current ticket.", inline=True)
        embed.add_field(name="/rename `name`", value="Changes the ticket name.", inline=True)
        embed.add_field(name="/claim", value="Claim or unclaim the ticket.", inline=True)
        embed.add_field(name="/closerequest", value="Sends a message asking the user to confirm the ticket can be closed.", inline=True)
        embed.add_field(name="/transcript", value="Generates a transcript of the ticket.", inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCommand(bot))
