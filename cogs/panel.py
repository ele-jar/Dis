import discord
from discord.ext import commands
from discord import app_commands, ui
import sqlite3

# --- Modals for Text Input ---
class PanelTextModal(ui.Modal):
    response_text = ui.TextInput(label="Custom Text", style=discord.TextStyle.paragraph, max_length=1024)

    def __init__(self, *, title: str, view: 'PanelConfigurationView', target_key: str) -> None:
        super().__init__(title=title)
        self.view = view
        self.target_key = target_key
        self.response_text.label = title
        if default_text := self.view.panel_data.get(self.target_key):
            self.response_text.default = default_text

    async def on_submit(self, interaction: discord.Interaction):
        self.view.panel_data[self.target_key] = self.response_text.value
        await self.view.update_view(interaction)

# --- Main Configuration View ---
class PanelConfigurationView(ui.View):
    def __init__(self, bot: commands.Bot, author: discord.Member, panel_id: int = None):
        super().__init__(timeout=600)
        self.bot = bot
        self.author = author
        self.panel_id = panel_id
        self.message = None
        self.old_panel_message_id = None
        self.old_panel_channel_id = None
        self.panel_data = {
            "name": "Support Ticket", "support_role": None, "category": None,
            "transcript_channel": None, "panel_channel": None, "claimable": False,
            "panel_description": "To create a ticket, use the button below.",
            "button_text": "Create Ticket",
            "welcome_message": "Support will be with you shortly. To close this ticket, press the button below."
        }
        self.required_fields = ["support_role", "category", "transcript_channel", "panel_channel"]

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
                await self.message.edit(content="This panel configuration has expired.", view=self)
            except discord.NotFound:
                pass

    async def start(self, interaction: discord.Interaction):
        if self.panel_id:
            await self.load_panel_data(interaction.guild)
        self.populate_components()
        embed = self.create_embed()
        await interaction.response.send_message(embed=embed, view=self, ephemeral=True)
        self.message = await interaction.original_response()

    async def load_panel_data(self, guild: discord.Guild):
        with sqlite3.connect(self.bot.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM panels WHERE panel_id = ?", (self.panel_id,))
            data = cursor.fetchone()
            if data:
                self.old_panel_message_id = data["message_id"]
                self.old_panel_channel_id = data["channel_id"]
                self.panel_data = {
                    "name": data["panel_name"],
                    "support_role": guild.get_role(data["support_role_id"]),
                    "category": guild.get_channel(data["category_id"]),
                    "transcript_channel": guild.get_channel(data["transcript_channel_id"]),
                    "panel_channel": guild.get_channel(data["channel_id"]),
                    "claimable": bool(data["is_claimable"]),
                    "panel_description": data["panel_description"],
                    "button_text": data["button_text"],
                    "welcome_message": data["welcome_message"],
                }

    def _get_val(self, key):
        val = self.panel_data.get(key)
        if isinstance(val, (discord.Role, discord.TextChannel, discord.CategoryChannel)):
            return val.mention
        if val is None:
            return "❌ Not Set"
        return str(val)

    def create_embed(self):
        title = f"Editing Panel: {self.panel_data['name']}" if self.panel_id else "Creating New Ticket Panel"
        embed = discord.Embed(title=title, description="Configure the settings below. Required fields are marked with `*`.", color=discord.Color.blurple())
        
        embed.add_field(name="Panel Name", value=self.panel_data["name"])
        embed.add_field(name="* Support Role", value=self._get_val("support_role"))
        embed.add_field(name="Ticket Claiming", value="Enabled" if self.panel_data["claimable"] else "Disabled")
        embed.add_field(name="* Ticket Category", value=self._get_val("category"), inline=False)
        embed.add_field(name="* Transcript Channel", value=self._get_val("transcript_channel"))
        embed.add_field(name="* Panel Channel", value=self._get_val("panel_channel"))

        desc = self.panel_data['panel_description']
        embed.add_field(name="Panel Description", value=f"```{desc[:200]}...```" if len(desc) > 200 else f"```{desc}```", inline=False)
        embed.add_field(name="Button Text", value=self.panel_data['button_text'])
        welcome = self.panel_data['welcome_message']
        embed.add_field(name="Welcome Message", value=f"```{welcome[:200]}...```" if len(welcome) > 200 else f"```{welcome}```", inline=False)
        
        return embed

    def all_required_filled(self):
        return all(self.panel_data.get(key) is not None for key in self.required_fields)

    def populate_components(self):
        self.clear_items()
        
        self.add_item(self.RoleSelect(default=self.panel_data.get("support_role")))
        self.add_item(self.CategorySelect(default=self.panel_data.get("category")))
        self.add_item(self.ChannelSelect(target_key="transcript_channel", placeholder="Select a transcript channel...", default=self.panel_data.get("transcript_channel")))
        self.add_item(self.ChannelSelect(target_key="panel_channel", placeholder="Select a panel channel...", default=self.panel_data.get("panel_channel")))
        self.add_item(self.SetTextButton("Set Panel Name", "name"))
        self.add_item(self.SetTextButton("Set Panel Description", "panel_description"))
        self.add_item(self.SetTextButton("Set Button Text", "button_text"))
        self.add_item(self.SetTextButton("Set Welcome Message", "welcome_message"))
        self.add_item(self.ToggleClaimButton())
        self.add_item(self.CancelButton())
        save_button = self.SaveButton(is_editing=bool(self.panel_id))
        save_button.disabled = not self.all_required_filled()
        self.add_item(save_button)

    async def update_view(self, interaction: discord.Interaction):
        self.populate_components()
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    # --- Components ---
    class RoleSelect(ui.RoleSelect):
        def __init__(self, default: discord.Role = None):
            super().__init__(placeholder="Select a support role...", row=0)
            if default: self.default_values = [discord.Object(id=default.id)]
        async def callback(self, interaction: discord.Interaction):
            self.view.panel_data['support_role'] = self.values[0]
            await self.view.update_view(interaction)

    class CategorySelect(ui.ChannelSelect):
        def __init__(self, default: discord.CategoryChannel = None):
            super().__init__(placeholder="Select a ticket category...", channel_types=[discord.ChannelType.category], row=1)
            if default: self.default_values = [discord.Object(id=default.id)]
        async def callback(self, interaction: discord.Interaction):
            self.view.panel_data['category'] = self.values[0]
            await self.view.update_view(interaction)
            
    class ChannelSelect(ui.ChannelSelect):
        def __init__(self, target_key: str, placeholder: str, default: discord.TextChannel = None):
            super().__init__(placeholder=placeholder, channel_types=[discord.ChannelType.text], row=2)
            self.target_key = target_key
            if default: self.default_values = [discord.Object(id=default.id)]
        async def callback(self, interaction: discord.Interaction):
            self.view.panel_data[self.target_key] = self.values[0]
            await self.view.update_view(interaction)

    class SetTextButton(ui.Button):
        def __init__(self, label: str, target_key: str):
            super().__init__(label=label, style=discord.ButtonStyle.secondary, row=3)
            self.target_key = target_key
        async def callback(self, interaction: discord.Interaction):
            await interaction.response.send_modal(PanelTextModal(title=self.label, view=self.view, target_key=self.target_key))

    class ToggleClaimButton(ui.Button):
        def __init__(self):
            super().__init__(label="Toggle Claiming", style=discord.ButtonStyle.secondary, row=3)
        async def callback(self, interaction: discord.Interaction):
            self.view.panel_data['claimable'] = not self.view.panel_data['claimable']
            await self.view.update_view(interaction)

    class CancelButton(ui.Button):
        def __init__(self):
            super().__init__(label="Cancel", style=discord.ButtonStyle.red, row=4)
        async def callback(self, interaction: discord.Interaction):
            await interaction.response.edit_message(content="Operation cancelled.", embed=None, view=None)
            self.view.stop()

    class SaveButton(ui.Button):
        def __init__(self, is_editing: bool = False):
            label = "Save Changes" if is_editing else "Save and Create Panel"
            super().__init__(label=label, style=discord.ButtonStyle.green, row=4)
        async def callback(self, interaction: discord.Interaction):
            pd = self.view.panel_data
            panel_channel = pd['panel_channel']
            await interaction.response.edit_message(content="Saving panel...", embed=None, view=None)

            # **IMPROVEMENT**: Delete the old panel message if it exists
            if self.view.panel_id and self.view.old_panel_channel_id and self.view.old_panel_message_id:
                try:
                    old_channel = self.view.bot.get_channel(self.view.old_panel_channel_id)
                    if old_channel:
                        old_message = await old_channel.fetch_message(self.view.old_panel_message_id)
                        await old_message.delete()
                except (discord.NotFound, discord.Forbidden):
                    pass # Ignore if message is already gone or we can't access it

            panel_embed = discord.Embed(title=pd['name'], description=pd['panel_description'], color=discord.Color.green())
            ticket_view = self.view.bot.get_cog('TicketSystem').CreateTicketView()
            ticket_view.children[0].label = pd['button_text']
            
            try:
                panel_message = await panel_channel.send(embed=panel_embed, view=ticket_view)
            except (discord.Forbidden, discord.HTTPException) as e:
                await interaction.followup.send(f"Error: Could not send panel message to {panel_channel.mention}. Please check my permissions.\n`{e}`", ephemeral=True)
                return

            with sqlite3.connect(self.view.bot.db_path) as conn:
                cursor = conn.cursor()
                params = (
                    interaction.guild.id, pd['name'], panel_message.id, panel_channel.id,
                    pd['support_role'].id, pd['category'].id, pd['transcript_channel'].id,
                    1 if pd['claimable'] else 0, pd['panel_description'], pd['button_text'], pd['welcome_message']
                )
                if self.view.panel_id:
                    cursor.execute("""
                        UPDATE panels SET guild_id=?, panel_name=?, message_id=?, channel_id=?, support_role_id=?,
                        category_id=?, transcript_channel_id=?, is_claimable=?, panel_description=?,
                        button_text=?, welcome_message=? WHERE panel_id=?
                    """, (*params, self.view.panel_id))
                    msg = f"Panel '{pd['name']}' updated successfully in {panel_channel.mention}!"
                else:
                    cursor.execute("""
                        INSERT INTO panels (guild_id, panel_name, message_id, channel_id, support_role_id, category_id,
                        transcript_channel_id, is_claimable, panel_description, button_text, welcome_message)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, params)
                    msg = f"Panel '{pd['name']}' created successfully in {panel_channel.mention}!"
                conn.commit()
            
            await interaction.followup.send(msg, ephemeral=True)
            self.view.stop()

# --- Panel Selection View for /editpanel ---
class PanelSelectView(ui.View):
    def __init__(self, bot: commands.Bot, author: discord.Member, panels: list):
        super().__init__(timeout=180)
        self.bot = bot
        self.author = author
        self.add_item(self.PanelSelect(panels))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.author.id:
            return True
        await interaction.response.send_message("You cannot interact with this menu.", ephemeral=True)
        return False
        
    class PanelSelect(ui.Select):
        def __init__(self, panels: list):
            options = [discord.SelectOption(label=p['panel_name'], value=str(p['panel_id'])) for p in panels]
            super().__init__(placeholder="Choose a panel to edit...", options=options)
        
        async def callback(self, interaction: discord.Interaction):
            panel_id = int(self.values[0])
            await interaction.message.delete()
            
            edit_view = PanelConfigurationView(self.view.bot, self.view.author, panel_id)
            await edit_view.start(interaction)

class Panel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setup", description="Create a new ticket panel.")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup(self, interaction: discord.Interaction):
        view = PanelConfigurationView(self.bot, interaction.user)
        await view.start(interaction)
        
    @app_a pp_commands.command(name="editpanel", description="Edit an existing ticket panel.")
    @app_commands.checks.has_permissions(administrator=True)
    async def editpanel(self, interaction: discord.Interaction):
        with sqlite3.connect(self.bot.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT panel_id, panel_name FROM panels WHERE guild_id = ?", (interaction.guild.id,))
            panels = cursor.fetchall()

        if not panels:
            return await interaction.response.send_message("No panels found on this server to edit.", ephemeral=True)

        view = PanelSelectView(self.bot, interaction.user, panels)
        await interaction.response.send_message("Please select a panel to edit from the dropdown below.", view=view, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Panel(bot))
