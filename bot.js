require('dotenv').config();
const {
    Client,
    GatewayIntentBits,
    PermissionsBitField,
    ChannelType
} = require('discord.js');
const express = require('express');
const cors = require('cors');

const BOT_TOKEN = process.env.BOT_TOKEN;
const WEB_TOKEN = process.env.WEB_TOKEN;
const PORT = process.env.PORT || 3000;

if (!BOT_TOKEN || !WEB_TOKEN) {
    console.error("Error: BOT_TOKEN and WEB_TOKEN must be set in the .env file.");
    process.exit(1);
}

const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMembers,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent,
    ],
});

const app = express();
app.use(cors());
app.use(express.json());

const authMiddleware = (req, res, next) => {
    const authHeader = req.headers.authorization;
    if (authHeader && authHeader === WEB_TOKEN) {
        next();
    } else {
        res.status(401).json({ success: false, message: 'Unauthorized' });
    }
};

app.get('/', (req, res) => {
    res.sendFile(__dirname + '/index.html');
});

app.post('/api/auth', (req, res) => {
    if (req.body.token && req.body.token === WEB_TOKEN) {
        res.json({ success: true, message: 'Authentication successful' });
    } else {
        res.status(401).json({ success: false, message: 'Invalid web token' });
    }
});

app.use(authMiddleware);

app.get('/api/guilds', (req, res) => {
    const guilds = client.guilds.cache.map(guild => ({
        id: guild.id,
        name: guild.name,
        icon: guild.iconURL(),
    }));
    res.json(guilds);
});

const guildRouter = express.Router({ mergeParams: true });

async function getGuild(req, res, next) {
    try {
        req.guild = await client.guilds.fetch(req.params.guildId);
        if (!req.guild) return res.status(404).json({ success: false, message: 'Guild not found' });
        next();
    } catch (e) {
        res.status(404).json({ success: false, message: 'Guild not found' });
    }
}

guildRouter.get('/settings', (req, res) => {
    const guild = req.guild;
    res.json({
        name: guild.name,
        region: guild.preferredLocale,
        verificationLevel: guild.verificationLevel,
        explicitContentFilter: guild.explicitContentFilter,
        defaultMessageNotifications: guild.defaultMessageNotifications,
    });
});

guildRouter.patch('/settings', async (req, res) => {
    try {
        await req.guild.edit(req.body);
        res.json({ success: true, message: 'Guild settings updated' });
    } catch (e) {
        res.status(500).json({ success: false, message: e.message });
    }
});

guildRouter.get('/channels', (req, res) => {
    const channels = req.guild.channels.cache.map(ch => ({
        id: ch.id,
        name: ch.name,
        type: ch.type,
        position: ch.position,
        parentId: ch.parentId,
        topic: ch.topic,
    }));
    res.json(channels);
});

guildRouter.post('/channels', async (req, res) => {
    try {
        const { name, type, parentId, topic } = req.body;
        const channelTypeMap = { 'text': ChannelType.GuildText, 'voice': ChannelType.GuildVoice, 'category': ChannelType.GuildCategory };
        await req.guild.channels.create({
            name,
            type: channelTypeMap[type],
            parent: parentId || null,
            topic: topic || null,
        });
        res.json({ success: true, message: 'Channel created' });
    } catch (e) {
        res.status(500).json({ success: false, message: e.message });
    }
});

guildRouter.get('/roles', (req, res) => {
    const roles = req.guild.roles.cache.map(role => ({
        id: role.id,
        name: role.name,
        color: role.color,
        hoist: role.hoist,
        position: role.position,
        permissions: role.permissions.bitfield.toString(),
    }));
    res.json(roles);
});

guildRouter.post('/roles', async (req, res) => {
    try {
        const { name, color, hoist, position, permissions } = req.body;
        await req.guild.roles.create({
            name,
            color,
            hoist,
            position,
            permissions: PermissionsBitField.resolve(BigInt(permissions)),
        });
        res.json({ success: true, message: 'Role created' });
    } catch (e) {
        res.status(500).json({ success: false, message: e.message });
    }
});

guildRouter.get('/members', async (req, res) => {
    try {
        const members = await req.guild.members.fetch();
        const memberData = members.map(member => ({
            id: member.id,
            username: member.user.username,
            discriminator: member.user.discriminator,
            nickname: member.nickname,
            avatar: member.user.displayAvatarURL(),
            joinedAt: member.joinedAt,
        }));
        res.json(memberData);
    } catch (e) {
        res.status(500).json({ success: false, message: e.message });
    }
});

app.use('/api/guilds/:guildId', getGuild, guildRouter);

app.patch('/api/channels/:channelId', async (req, res) => {
    try {
        const channel = await client.channels.fetch(req.params.channelId);
        await channel.edit(req.body);
        res.json({ success: true, message: 'Channel updated' });
    } catch (e) {
        res.status(500).json({ success: false, message: e.message });
    }
});

app.delete('/api/channels/:channelId', async (req, res) => {
    try {
        const channel = await client.channels.fetch(req.params.channelId);
        await channel.delete();
        res.json({ success: true, message: 'Channel deleted' });
    } catch (e) {
        res.status(500).json({ success: false, message: e.message });
    }
});

app.get('/api/channels/:channelId/messages', async (req, res) => {
    try {
        const channel = await client.channels.fetch(req.params.channelId);
        const messages = await channel.messages.fetch({ limit: req.query.limit || 50 });
        const messageData = messages.map(msg => ({
            id: msg.id,
            content: msg.content,
            timestamp: msg.createdAt,
            author: { username: msg.author.username, discriminator: msg.author.discriminator },
            attachments: msg.attachments.map(a => ({ url: a.url, filename: a.name, size: a.size })),
        }));
        res.json(messageData);
    } catch (e) {
        res.status(500).json({ success: false, message: e.message });
    }
});

app.post('/api/channels/:channelId/messages', async (req, res) => {
    try {
        const channel = await client.channels.fetch(req.params.channelId);
        const { content, embed } = req.body;
        const payload = {};
        if (content) payload.content = content;
        if (embed) payload.embeds = [embed];
        await channel.send(payload);
        res.json({ success: true, message: 'Message sent' });
    } catch (e) {
        res.status(500).json({ success: false, message: e.message });
    }
});

app.delete('/api/channels/:channelId/messages/:messageId', async (req, res) => {
    try {
        const channel = await client.channels.fetch(req.params.channelId);
        const message = await channel.messages.fetch(req.params.messageId);
        await message.delete();
        res.json({ success: true, message: 'Message deleted' });
    } catch (e) {
        res.status(500).json({ success: false, message: e.message });
    }
});

async function getGuildAndMemberOrRole(req, res, next) {
    try {
        req.guild = await client.guilds.fetch(req.params.guildId);
        if (req.params.memberId) {
            req.target = await req.guild.members.fetch(req.params.memberId);
        } else if (req.params.roleId) {
            req.target = await req.guild.roles.fetch(req.params.roleId);
        }
        if (!req.guild || !req.target) return res.status(404).json({ success: false, message: 'Not found' });
        next();
    } catch (e) {
        res.status(404).json({ success: false, message: 'Guild, Member or Role not found' });
    }
}

const modRouter = express.Router({ mergeParams: true });

modRouter.patch('/roles/:roleId', async (req, res) => {
    try {
        const { name, color, hoist, position, permissions } = req.body;
        await req.target.edit({
            name,
            color,
            hoist,
            position,
            permissions: PermissionsBitField.resolve(BigInt(permissions)),
        });
        res.json({ success: true, message: 'Role updated' });
    } catch (e) {
        res.status(500).json({ success: false, message: e.message });
    }
});

modRouter.delete('/roles/:roleId', async (req, res) => {
    try {
        await req.target.delete();
        res.json({ success: true, message: 'Role deleted' });
    } catch (e) {
        res.status(500).json({ success: false, message: e.message });
    }
});

modRouter.post('/members/:memberId/kick', async (req, res) => {
    try {
        await req.target.kick(req.body.reason);
        res.json({ success: true, message: 'Member kicked' });
    } catch (e) {
        res.status(500).json({ success: false, message: e.message });
    }
});

modRouter.post('/members/:memberId/ban', async (req, res) => {
    try {
        await req.target.ban({
            reason: req.body.reason,
            deleteMessageSeconds: req.body.deleteMessageDays ? req.body.deleteMessageDays * 86400 : 0,
        });
        res.json({ success: true, message: 'Member banned' });
    } catch (e) {
        res.status(500).json({ success: false, message: e.message });
    }
});

app.use('/api/guilds/:guildId', getGuildAndMemberOrRole, modRouter);

client.on('ready', () => {
    console.log(`Logged in as ${client.user.tag}!`);
    console.log(`Bot is ready and connected to Discord.`);
    app.listen(PORT, () => {
        console.log(`Web server listening at http://localhost:${PORT}`);
        console.log('Access the panel from a browser on the same network.');
    });
});

client.login(BOT_TOKEN);
