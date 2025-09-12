import discord
from discord.ext import commands
from discord import app_commands, ui

class PanelNameModal(ui.Modal, title='Set Panel Name'):
    panel_name = ui.TextInput(label='Panel Name', placeholder='e.g., General Support', required=True, max_length=100)

    def __init__(self, setup_view):
        super().__init__()
        self.setup_view = setup_view

    async def on_submit(self, interaction: discord.Interaction):
        self.setup_view.panel_data['name'] = self.panel_name.value
        await interaction.response.defer()
        await self.setup_view.update_view(interaction)

class SetupView(ui.View):
    def __init__(self, bot, author):
        super().__init__(timeout=300)
        self.bot = bot
        self.author = author
        self.current_step = 1
        self.message = None
        self.panel_data = {
            "name": "New Panel", "support_role": None, "category": None,
            "transcript_channel": None, "panel_channel": None, "claimable": False
        }

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
            self.add_item(ui.Button(label="Set Name", style=discord.ButtonStyle.secondary, custom_id="set_name"))
        elif self.current_step == 2:
            self.add_item(ui.RoleSelect(placeholder="Select a support role...", custom_id="role_select"))
            is_claimable = self.panel_data['claimable']
            self.add_item(ui.Button(
                label="Disable Claiming" if is_claimable else "Enable Claiming",
                style=discord.ButtonStyle.red if is_claimable else discord.ButtonStyle.green,
                custom_id="toggle_claim"
            ))
        elif self.current_step == 3:
            self.add_item(ui.ChannelSelect(placeholder="Select a category...", channel_types=[discord.ChannelType.category], custom_id="category_select"))
        elif self.current_step == 4:
            self.add_item(ui.ChannelSelect(placeholder="Select a transcript channel...", channel_types=[discord.ChannelType.text], custom_id="transcript_select"))
        elif self.current_step == 5:
            self.add_item(ui.ChannelSelect(placeholder="Select a panel channel...", channel_types=[discord.ChannelType.text], custom_id="panel_channel_select"))

        if self.current_step > 1:
            self.add_item(ui.Button(label="Back", style=discord.ButtonStyle.grey, custom_id="back", row=4))
        
        next_label = "Finish" if self.current_step == 5 else "Save & Continue"
        self.add_item(ui.Button(label=next_label, style=discord.ButtonStyle.green, custom_id="next", row=4))
        self.add_item(ui.Button(label="Cancel", style=discord.ButtonStyle.red, custom_id="cancel", row=4))

    async def update_view(self, interaction: discord.Interaction):
        self.update_components()
        embed = self.create_embed()
        try:
            await interaction.message.edit(embed=embed, view=self)
        except discord.NotFound:
            # The original message was likely dismissed by the user.
            pass

    async def dispatch_interaction(self, interaction: discord.Interaction):
        custom_id = interaction.data['custom_id']
        
        if custom_id == "set_name":
            await interaction.response.send_modal(PanelNameModal(self))
            return
        elif 'select' in custom_id:
            value = interaction.data['values'][0]
            if custom_id == 'role_select': self.panel_data['support_role'] = interaction.guild.get_role(int(value))
            else:
                channel = interaction.guild.get_channel(int(value))
                if custom_id == 'category_select': self.panel_data['category'] = channel
                elif custom_id == 'transcript_select': self.panel_data['transcript_channel'] = channel
                elif custom_id == 'panel_channel_select': self.panel_data['panel_channel'] = channel
        elif custom_id == "toggle_claim":
            self.panel_data['claimable'] = not self.panel_data['claimable']
        elif custom_id == "back":
            self.current_step -= 1
        elif custom_id == "cancel":
            try: await interaction.message.delete()
            except discord.NotFound: pass
            await interaction.response.send_message("Panel creation cancelled.", ephemeral=True)
            self.stop()
            return
        elif custom_id == "next":
            if self.current_step == 5:
                pd = self.panel_data
                if not all([pd['support_role'], pd['category'], pd['transcript_channel'], pd['panel_channel']]):
                    return await interaction.response.send_message("Please complete all fields before finishing.", ephemeral=True)
                
                await interaction.response.defer()
                conn, cursor = self.bot.get_db_connection()
                cursor.execute("INSERT INTO panels (guild_id, panel_name, support_role_id, category_id, transcript_channel_id, channel_id, is_claimable) VALUES (?, ?, ?, ?, ?, ?, ?)",
                               (interaction.guild.id, pd['name'], pd['support_role'].id, pd['category'].id, pd['transcript_channel'].id, pd['panel_channel'].id, 1 if pd['claimable'] else 0))
                panel_id = cursor.lastrowid
                conn.commit()

                panel_embed = discord.Embed(title=pd['name'], description="To create a ticket, use the button below.", color=discord.Color.green())
                panel_message = await pd['panel_channel'].send(embed=panel_embed, view=self.bot.get_cog('TicketSystem').CreateTicketView())
                
                cursor.execute("UPDATE panels SET message_id = ? WHERE panel_id = ?", (panel_message.id, panel_id))
                conn.commit()
                
                try: await interaction.message.delete()
                except discord.NotFound: pass

                await interaction.followup.send(f"Panel '{pd['name']}' created successfully in {pd['panel_channel'].mention}!", ephemeral=True)
                self.stop()
                return
            else:
                self.current_step += 1
        
        if not interaction.response.is_done():
            await interaction.response.defer()
        await self.update_view(interaction)

class Panel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setup", description="Create a new ticket panel.")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup(self, interaction: discord.Interaction):
        view = SetupView(self.bot, interaction.user)
        view.update_components()
        embed = view.create_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await interaction.original_response()

        async def view_interaction_handler(inter):
            if inter.message and view.message and inter.message.id == view.message.id:
                 await view.dispatch_interaction(inter)
        
        # This listener is now safe because the view manages its own state
        self.bot.add_listener(view_interaction_handler, 'on_interaction')
        view.on_timeout = lambda: self.bot.remove_listener(view_interaction_handler, 'on_interaction')


async def setup(bot: commands.Bot):
    await bot.add_cog(Panel(bot))
