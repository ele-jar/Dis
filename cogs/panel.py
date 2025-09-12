import discord
from discord.ext import commands
from discord import app_commands, ui

class TextInputModal(ui.Modal):
    response_text = ui.TextInput(label="Custom Text", style=discord.TextStyle.paragraph, max_length=1024)

    def __init__(self, *, title: str, view: ui.View, target_key: str, default_text: str) -> None:
        super().__init__(title=title)
        self.view = view
        self.target_key = target_key
        self.response_text.placeholder = default_text

    async def on_submit(self, interaction: discord.Interaction):
        self.view.panel_data[self.target_key] = self.response_text.value
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
            "transcript_channel": None, "panel_channel": None, "claimable": False,
            "panel_description": None, "button_text": None, "welcome_message": None
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
            "Select the channel to send the final ticket panel into.",
            "Set the description text for the panel (supports Markdown).",
            "Set the text for the ticket creation button.",
            "Set the welcome message for new tickets (supports Markdown)."
        ]
        embed = discord.Embed(
            title=f"Step {self.current_step}/8: Configure Ticket Panel",
            description=descriptions[self.current_step - 1],
            color=discord.Color.blurple()
        )
        embed.add_field(name="Panel Name", value=self.panel_data['name'], inline=False)
        role_val = self.panel_data['support_role'].mention if self.panel_data['support_role'] else "None"
        embed.add_field(name="Support Role", value=role_val)
        embed.add_field(name="Ticket Claiming", value="Enabled" if self.panel_data['claimable'] else "Disabled")
        cat_val = self.panel_data['category'].mention if self.panel_data['category'] else "None"
        embed.add_field(name="Ticket Category", value=cat_val, inline=False)
        trans_val = self.panel_data['transcript_channel'].mention if self.panel_data['transcript_channel'] else "None"
        embed.add_field(name="Transcript Channel", value=trans_val)
        
        desc_val = self.panel_data['panel_description'] or "Default"
        embed.add_field(name="Panel Description", value=f"```{desc_val[:100]}...```" if self.panel_data['panel_description'] and len(desc_val) > 100 else desc_val, inline=False)
        button_val = self.panel_data['button_text'] or "Default"
        embed.add_field(name="Button Text", value=button_val, inline=False)
        welcome_val = self.panel_data['welcome_message'] or "Default"
        embed.add_field(name="Welcome Message", value=f"```{welcome_val[:100]}...```" if self.panel_data['welcome_message'] and len(welcome_val) > 100 else welcome_val, inline=False)
        
        return embed

    def update_components(self):
        self.clear_items()
        
        if self.current_step == 1: self.add_item(self.SetNameButton())
        elif self.current_step == 2:
            self.add_item(self.RoleSelect())
            self.add_item(self.ToggleClaimButton())
        elif self.current_step == 3: self.add_item(self.CategorySelect())
        elif self.current_step == 4: self.add_item(self.TranscriptChannelSelect())
        elif self.current_step == 5: self.add_item(self.PanelChannelSelect())
        elif self.current_step == 6:
            self.add_item(self.SetTextButton("Set Panel Description", "panel_description", "To create a ticket, use the button below."))
            self.add_item(self.SkipButton())
        elif self.current_step == 7:
            self.add_item(self.SetTextButton("Set Button Text", "button_text", "Create Ticket"))
            self.add_item(self.SkipButton())
        elif self.current_step == 8:
            self.add_item(self.SetTextButton("Set Welcome Message", "welcome_message", "Support will be with you shortly..."))
            self.add_item(self.SkipButton())

        if self.current_step > 1: self.add_item(self.BackButton())
        self.add_item(self.NextButton())
        self.add_item(self.CancelButton())
    
    async def update_message(self):
        self.update_components()
        embed = self.create_embed()
        if self.message: await self.message.edit(embed=embed, view=self)

    class SetTextButton(ui.Button):
        def __init__(self, label: str, target_key: str, default_text: str):
            super().__init__(label=label, style=discord.ButtonStyle.secondary)
            self.target_key = target_key
            self.default_text = default_text
        async def callback(self, interaction: discord.Interaction):
            modal = TextInputModal(title=self.label, view=self.view, target_key=self.target_key, default_text=self.default_text)
            await interaction.response.send_modal(modal)

    class SkipButton(ui.Button):
        def __init__(self): super().__init__(label="Skip", style=discord.ButtonStyle.grey)
        async def callback(self, interaction: discord.Interaction):
            self.view.current_step += 1
            await interaction.response.defer()
            await self.view.update_message()

    class SetNameButton(ui.Button):
        def __init__(self): super().__init__(label="Set Name", style=discord.ButtonStyle.secondary)
        async def callback(self, interaction: discord.Interaction):
            modal = TextInputModal(title="Set Panel Name", view=self.view, target_key="name", default_text="General Support")
            await interaction.response.send_modal(modal)

    class RoleSelect(ui.RoleSelect):
        def __init__(self): super().__init__(placeholder="Select a support role...")
        async def callback(self, interaction: discord.Interaction):
            self.view.panel_data['support_role'] = self.values[0]
            await interaction.response.defer()
            await self.view.update_message()

    class ToggleClaimButton(ui.Button):
        def __init__(self): super().__init__(label="Toggle Claiming")
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
        def __init__(self): super().__init__(label="Next", style=discord.ButtonStyle.green, row=4)
        @property
        def label(self): return "Finish" if self.view.current_step == 8 else "Next"
        
        async def callback(self, interaction: discord.Interaction):
            if self.view.current_step == 8:
                pd = self.view.panel_data
                if not all([pd['support_role'], pd['category'], pd['transcript_channel'], pd['panel_channel']]):
                    return await interaction.response.send_message("Please complete all required fields before finishing.", ephemeral=True)
                
                await interaction.response.defer(ephemeral=True)
                panel_channel_obj = interaction.guild.get_channel(pd['panel_channel'].id)
                if not panel_channel_obj: return await interaction.followup.send("Error: The selected panel channel could not be found.", ephemeral=True)

                conn, cursor = self.view.bot.get_db_connection()
                
                desc = pd['panel_description'] or "To create a ticket, use the button below."
                btn_text = pd['button_text'] or "Create Ticket"
                welcome = pd['welcome_message'] or "Support will be with you shortly. To close this ticket, press the button below."

                cursor.execute("INSERT INTO panels (guild_id, panel_name, support_role_id, category_id, transcript_channel_id, channel_id, is_claimable, panel_description, button_text, welcome_message) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                               (interaction.guild.id, pd['name'], pd['support_role'].id, pd['category'].id, pd['transcript_channel'].id, panel_channel_obj.id, 1 if pd['claimable'] else 0, desc, btn_text, welcome))
                panel_id = cursor.lastrowid
                conn.commit()

                panel_embed = discord.Embed(title=pd['name'], description=desc, color=discord.Color.green())
                
                # Create a temporary view just to set the button label
                temp_view = self.view.bot.get_cog('TicketSystem').CreateTicketView()
                temp_view.children[0].label = btn_text

                panel_message = await panel_channel_obj.send(embed=panel_embed, view=temp_view)
                
                cursor.execute("UPDATE panels SET message_id = ? WHERE panel_id = ?", (panel_message.id, panel_id))
                conn.commit()
                
                await self.view.message.delete()
                await interaction.followup.send(f"Panel '{pd['name']}' created successfully in {panel_channel_obj.mention}!", ephemeral=True)
                self.view.stop()
            else:
                self.view.current_step += 1
                await interaction.response.defer()
                await self.view.update_message()

    class CancelButton(ui.Button):
        def __init__(self): super().__init__(label="Cancel", style=discord.ButtonStyle.red, row=4)
        async def callback(self, interaction: discord.Interaction):
            await self.view.message.delete()
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
