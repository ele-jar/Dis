import discord
from discord.ext import commands
from discord import app_commands, ui

# FIX 1: The Modal now correctly accepts the view that created it.
class PanelNameModal(ui.Modal):
    panel_name_input = ui.TextInput(label='Panel Name', placeholder='e.g., General Support', required=True, max_length=100)

    def __init__(self, *, title: str = "Set Panel Name", view: ui.View) -> None:
        super().__init__(title=title)
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        self.view.panel_data['name'] = self.panel_name_input.value
        await self.view.update_message()
        await interaction.response.defer()

class SetupView(ui.View):
    def __init__(self, bot, author):
        super().__init__(timeout=300)
        self.bot = bot
        self.author = author
        self.message = None
        self.current_step = 1
        self.panel_data = {
            "name": "New Panel", "support_role": None, "category": None,
            "transcript_channel": None, "panel_channel": None, "claimable": False
        }
        self.update_components()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.author.id:
            return True
        await interaction.response.send_message("You cannot interact with this setup panel.", ephemeral=True)
        return False

    async def on_timeout(self):
        if self.message:
            for item in self.children:
                item.disabled = True
            try:
                await self.message.edit(content="This setup panel has expired.", view=self)
            except discord.NotFound:
                pass

    def create_embed(self):
        descriptions = [
            "Use the button to set the panel name.",
            "Select the support role and enable/disable ticket claiming.",
            "Select the category where new ticket channels will be created.",
            "Select the channel where transcripts will be saved.",
            "Select the channel to send the final ticket panel into."
        ]
        embed = discord.Embed(
            title=f"Step {self.current_step}/5: Configure Ticket Panel",
            description=descriptions[self.current_step - 1],
            color=discord.Color.blurple()
        )
        embed.add_field(name="Panel Name", value=self.panel_data['name'], inline=False)
        role_val = self.panel_data['support_role'].mention if self.panel_data['support_role'] else "None"
        embed.add_field(name="Support Role", value=role_val, inline=False)
        embed.add_field(name="Ticket Claiming", value="Enabled" if self.panel_data['claimable'] else "Disabled", inline=False)
        cat_val = self.panel_data['category'].mention if self.panel_data['category'] else "None"
        embed.add_field(name="Ticket Category", value=cat_val, inline=False)
        trans_val = self.panel_data['transcript_channel'].mention if self.panel_data['transcript_channel'] else "None"
        embed.add_field(name="Transcript Channel", value=trans_val, inline=False)
        return embed

    def update_components(self):
        self.clear_items()
        
        if self.current_step == 1:
            self.add_item(self.SetNameButton())
        elif self.current_step == 2:
            self.add_item(self.RoleSelect())
            self.add_item(self.ToggleClaimButton())
        elif self.current_step == 3:
            self.add_item(self.CategorySelect())
        elif self.current_step == 4:
            self.add_item(self.TranscriptChannelSelect())
        elif self.current_step == 5:
            self.add_item(self.PanelChannelSelect())

        if self.current_step > 1: self.add_item(self.BackButton())
        self.add_item(self.NextButton())
        self.add_item(self.CancelButton())
    
    async def update_message(self):
        self.update_components()
        embed = self.create_embed()
        try:
            if self.message:
                await self.message.edit(embed=embed, view=self)
        except discord.NotFound:
            pass

    class SetNameButton(ui.Button):
        def __init__(self): super().__init__(label="Set Name", style=discord.ButtonStyle.secondary)
        async def callback(self, interaction: discord.Interaction):
            # FIX 1: Pass the view correctly to the Modal's new constructor
            await interaction.response.send_modal(PanelNameModal(view=self.view))

    class RoleSelect(ui.RoleSelect):
        def __init__(self): super().__init__(placeholder="Select a support role...")
        async def callback(self, interaction: discord.Interaction):
            self.view.panel_data['support_role'] = self.values[0]
            await interaction.response.defer()
            await self.view.update_message()

    class ToggleClaimButton(ui.Button):
        def __init__(self):
            super().__init__(label="Toggle Claiming")
        async def callback(self, interaction: discord.Interaction):
            self.view.panel_data['claimable'] = not self.view.panel_data['claimable']
            await interaction.response.defer()
            await self.view.update_message()

    class CategorySelect(ui.ChannelSelect):
        def __init__(self): super().__init__(placeholder="Select a category...", channel_types=[discord.ChannelType.category])
        async def callback(self, interaction: discord.Interaction):
            self.view.panel_data['category'] = self.values[0]
            await interaction.response.defer()
            await self.view.update_message()

    class TranscriptChannelSelect(ui.ChannelSelect):
        def __init__(self): super().__init__(placeholder="Select a transcript channel...", channel_types=[discord.ChannelType.text])
        async def callback(self, interaction: discord.Interaction):
            self.view.panel_data['transcript_channel'] = self.values[0]
            await interaction.response.defer()
            await self.view.update_message()

    class PanelChannelSelect(ui.ChannelSelect):
        def __init__(self): super().__init__(placeholder="Select a panel channel...", channel_types=[discord.ChannelType.text])
        async def callback(self, interaction: discord.Interaction):
            self.view.panel_data['panel_channel'] = self.values[0]
            await interaction.response.defer()
            await self.view.update_message()

    class BackButton(ui.Button):
        def __init__(self): super().__init__(label="Back", style=discord.ButtonStyle.grey, row=4)
        async def callback(self, interaction: discord.Interaction):
            self.view.current_step -= 1
            await interaction.response.defer()
            await self.view.update_message()

    class NextButton(ui.Button):
        def __init__(self):
             super().__init__(label="Next", style=discord.ButtonStyle.green, row=4)
        
        @property
        def label(self):
            return "Save & Continue" if self.view.current_step == 5 else "Next"
        
        async def callback(self, interaction: discord.Interaction):
            if self.view.current_step == 5:
                pd = self.view.panel_data
                if not all([pd['support_role'], pd['category'], pd['transcript_channel'], pd['panel_channel']]):
                    return await interaction.response.send_message("Please complete all required fields before finishing.", ephemeral=True)
                
                await interaction.response.defer(ephemeral=True)

                # FIX 2: Get the full channel object from its ID before trying to send a message to it.
                panel_channel_obj = interaction.guild.get_channel(pd['panel_channel'].id)
                if not panel_channel_obj:
                    return await interaction.followup.send("Error: The selected panel channel could not be found.", ephemeral=True)

                conn, cursor = self.view.bot.get_db_connection()
                cursor.execute("INSERT INTO panels (guild_id, panel_name, support_role_id, category_id, transcript_channel_id, channel_id, is_claimable) VALUES (?, ?, ?, ?, ?, ?, ?)",
                               (interaction.guild.id, pd['name'], pd['support_role'].id, pd['category'].id, pd['transcript_channel'].id, panel_channel_obj.id, 1 if pd['claimable'] else 0))
                panel_id = cursor.lastrowid
                conn.commit()

                panel_embed = discord.Embed(title=pd['name'], description="To create a ticket, use the button below.", color=discord.Color.green())
                panel_message = await panel_channel_obj.send(embed=panel_embed, view=self.view.bot.get_cog('TicketSystem').CreateTicketView())
                
                cursor.execute("UPDATE panels SET message_id = ? WHERE panel_id = ?", (panel_message.id, panel_id))
                conn.commit()
                
                try: 
                    await self.view.message.delete()
                except discord.NotFound: 
                    pass
                
                await interaction.followup.send(f"Panel '{pd['name']}' created successfully in {panel_channel_obj.mention}!", ephemeral=True)
                self.view.stop()
            else:
                pd = self.view.panel_data
                if self.view.current_step == 2 and not pd['support_role']:
                    return await interaction.response.send_message("Please select a support role before proceeding.", ephemeral=True)
                if self.view.current_step == 3 and not pd['category']:
                    return await interaction.response.send_message("Please select a ticket category before proceeding.", ephemeral=True)
                if self.view.current_step == 4 and not pd['transcript_channel']:
                    return await interaction.response.send_message("Please select a transcript channel before proceeding.", ephemeral=True)

                self.view.current_step += 1
                await interaction.response.defer()
                await self.view.update_message()

    class CancelButton(ui.Button):
        def __init__(self): super().__init__(label="Cancel", style=discord.ButtonStyle.red, row=4)
        async def callback(self, interaction: discord.Interaction):
            try: 
                await self.view.message.delete()
            except discord.NotFound: 
                pass
            await interaction.response.send_message("Panel creation cancelled.", ephemeral=True)
            self.view.stop()

class Panel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setup", description="Create a new ticket panel.")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup(self, interaction: discord.Interaction):
        view = SetupView(self.bot, interaction.user)
        embed = view.create_embed()
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

async def setup(bot: commands.Bot):
    await bot.add_cog(Panel(bot))
