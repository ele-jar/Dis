import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import sqlite3
import asyncio

load_dotenv()

class TicketBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)
        self.db_path = os.path.join('db', 'database.sqlite')
        # DB connection is no longer stored on the bot object.
        # Connections will be made on-demand in cogs.

    def setup_database(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS panels (
                    panel_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    panel_name TEXT NOT NULL,
                    message_id INTEGER,
                    channel_id INTEGER,
                    support_role_id INTEGER NOT NULL,
                    category_id INTEGER NOT NULL,
                    transcript_channel_id INTEGER NOT NULL,
                    is_claimable INTEGER DEFAULT 0,
                    panel_description TEXT,
                    button_text TEXT,
                    welcome_message TEXT
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tickets (
                    ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    guild_id INTEGER NOT NULL,
                    panel_id INTEGER NOT NULL,
                    channel_id INTEGER NOT NULL,
                    owner_id INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    ticket_num INTEGER NOT NULL,
                    claimed_by_id INTEGER
                )
            ''')
            conn.commit()

    async def setup_hook(self):
        self.setup_database()
        
        initial_extensions = [
            'cogs.panel',
            'cogs.ticket_system',
            'cogs.ticket_commands',
            'cogs.help'
        ]
        for extension in initial_extensions:
            try:
                await self.load_extension(extension)
            except Exception as e:
                print(f'Failed to load extension {extension}.')
                print(e)
        
        # Views are added here to be persistent across restarts
        ticket_system_cog = self.get_cog('TicketSystem')
        if ticket_system_cog:
            self.add_view(ticket_system_cog.CreateTicketView())
            self.add_view(ticket_system_cog.OpenTicketView())
            self.add_view(ticket_system_cog.ClosedTicketView())
            self.add_view(ticket_system_cog.CloseRequestView())

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print('------')
        await self.tree.sync()

    # Removed get_db_connection method

bot = TicketBot()
bot.run(os.getenv('DISCORD_TOKEN'))
