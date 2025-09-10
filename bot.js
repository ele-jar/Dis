// bot.js
const Discord = require('discord.js');
const express = require('express');
const cors = require('cors');
require('dotenv').config();

// Initialize Discord client with necessary intents
const client = new Discord.Client({
    intents: [
        Discord.GatewayIntentBits.Guilds,
        Discord.GatewayIntentBits.GuildMembers,
        Discord.GatewayIntentBits.GuildBans,
        Discord.GatewayIntentBits.GuildEmojisAndStickers,
        Discord.GatewayIntentBits.GuildIntegrations,
        Discord.GatewayIntentBits.GuildWebhooks,
        Discord.GatewayIntentBits.GuildInvites,
        Discord.GatewayIntentBits.GuildVoiceStates,
        Discord.GatewayIntentBits.GuildPresences,
        Discord.GatewayIntentBits.GuildMessages,
        Discord.GatewayIntentBits.GuildMessageReactions,
        Discord.GatewayIntentBits.GuildMessageTyping,
        Discord.GatewayIntentBits.DirectMessages,
        Discord.GatewayIntentBits.DirectMessageReactions,
        Discord.GatewayIntentBits.DirectMessageTyping,
        Discord.GatewayIntentBits.MessageContent
    ]
});

// Initialize Express app for web server
const app = express();
app.use(cors());
app.use(express.json());

// Bot login
client.login(process.env.BOT_TOKEN);

// Ready event
client.once('ready', () => {
    console.log(`Logged in as ${client.user.tag}!`);
    client.user.setActivity('Server Management');
});

// Store web token for authentication
let webToken = '';

// API endpoint to authenticate web panel
app.post('/api/auth', (req, res) => {
    const { token } = req.body;
    if (token === process.env.WEB_TOKEN) {
        webToken = token;
        res.json({ success: true, message: 'Authentication successful' });
    } else {
        res.status(401).json({ success: false, message: 'Invalid token' });
    }
});

// Middleware to check authentication
const authenticate = (req, res, next) => {
    if (req.headers.authorization === webToken) {
        next();
    } else {
        res.status(401).json({ success: false, message: 'Unauthorized' });
    }
};

// API endpoint to get guilds
app.get('/api/guilds', authenticate, (req, res) => {
    const guilds = client.guilds.cache.map(guild => ({
        id: guild.id,
        name: guild.name,
        icon: guild.iconURL()
    }));
    res.json(guilds);
});

// API endpoint to get channels
app.get('/api/guilds/:guildId/channels', authenticate, (req, res) => {
    const guild = client.guilds.cache.get(req.params.guildId);
    if (!guild) {
        return res.status(404).json({ success: false, message: 'Guild not found' });
    }
    
    const channels = guild.channels.cache.map(channel => ({
        id: channel.id,
        name: channel.name,
        type: channel.type,
        position: channel.position,
        parentId: channel.parentId
    }));
    
    res.json(channels);
});

// API endpoint to create channel
app.post('/api/guilds/:guildId/channels', authenticate, async (req, res) => {
    try {
        const guild = client.guilds.cache.get(req.params.guildId);
        if (!guild) {
            return res.status(404).json({ success: false, message: 'Guild not found' });
        }
        
        const { name, type, parentId } = req.body;
        
        const channelOptions = {
            name,
            type: type === 'text' ? Discord.ChannelType.GuildText : 
                  type === 'voice' ? Discord.ChannelType.GuildVoice : 
                  Discord.ChannelType.GuildCategory
        };
        
        if (parentId) {
            channelOptions.parent = parentId;
        }
        
        const channel = await guild.channels.create(channelOptions);
        
        res.json({
            success: true,
            message: 'Channel created successfully',
            channel: {
                id: channel.id,
                name: channel.name,
                type: channel.type,
                position: channel.position,
                parentId: channel.parentId
            }
        });
    } catch (error) {
        console.error('Error creating channel:', error);
        res.status(500).json({ success: false, message: 'Failed to create channel', error: error.message });
    }
});

// API endpoint to edit channel
app.patch('/api/channels/:channelId', authenticate, async (req, res) => {
    try {
        const channel = client.channels.cache.get(req.params.channelId);
        if (!channel) {
            return res.status(404).json({ success: false, message: 'Channel not found' });
        }
        
        const { name, topic, position, parentId } = req.body;
        
        const updateOptions = {};
        if (name) updateOptions.name = name;
        if (topic) updateOptions.topic = topic;
        if (position !== undefined) updateOptions.position = position;
        if (parentId !== undefined) updateOptions.parent = parentId;
        
        await channel.edit(updateOptions);
        
        res.json({
            success: true,
            message: 'Channel updated successfully',
            channel: {
                id: channel.id,
                name: channel.name,
                type: channel.type,
                position: channel.position,
                parentId: channel.parentId
            }
        });
    } catch (error) {
        console.error('Error updating channel:', error);
        res.status(500).json({ success: false, message: 'Failed to update channel', error: error.message });
    }
});

// API endpoint to delete channel
app.delete('/api/channels/:channelId', authenticate, async (req, res) => {
    try {
        const channel = client.channels.cache.get(req.params.channelId);
        if (!channel) {
            return res.status(404).json({ success: false, message: 'Channel not found' });
        }
        
        await channel.delete();
        
        res.json({
            success: true,
            message: 'Channel deleted successfully'
        });
    } catch (error) {
        console.error('Error deleting channel:', error);
        res.status(500).json({ success: false, message: 'Failed to delete channel', error: error.message });
    }
});

// API endpoint to get roles
app.get('/api/guilds/:guildId/roles', authenticate, (req, res) => {
    const guild = client.guilds.cache.get(req.params.guildId);
    if (!guild) {
        return res.status(404).json({ success: false, message: 'Guild not found' });
    }
    
    const roles = guild.roles.cache.map(role => ({
        id: role.id,
        name: role.name,
        color: role.color,
        hoist: role.hoist,
        position: role.position,
        permissions: role.permissions.bitfield.toString()
    }));
    
    res.json(roles);
});

// API endpoint to create role
app.post('/api/guilds/:guildId/roles', authenticate, async (req, res) => {
    try {
        const guild = client.guilds.cache.get(req.params.guildId);
        if (!guild) {
            return res.status(404).json({ success: false, message: 'Guild not found' });
        }
        
        const { name, color, hoist, position, permissions } = req.body;
        
        const roleOptions = {};
        if (name) roleOptions.name = name;
        if (color) roleOptions.color = color;
        if (hoist !== undefined) roleOptions.hoist = hoist;
        if (position !== undefined) roleOptions.position = position;
        if (permissions) roleOptions.permissions = permissions;
        
        const role = await guild.roles.create(roleOptions);
        
        res.json({
            success: true,
            message: 'Role created successfully',
            role: {
                id: role.id,
                name: role.name,
                color: role.color,
                hoist: role.hoist,
                position: role.position,
                permissions: role.permissions.bitfield.toString()
            }
        });
    } catch (error) {
        console.error('Error creating role:', error);
        res.status(500).json({ success: false, message: 'Failed to create role', error: error.message });
    }
});

// API endpoint to edit role
app.patch('/api/guilds/:guildId/roles/:roleId', authenticate, async (req, res) => {
    try {
        const guild = client.guilds.cache.get(req.params.guildId);
        if (!guild) {
            return res.status(404).json({ success: false, message: 'Guild not found' });
        }
        
        const role = guild.roles.cache.get(req.params.roleId);
        if (!role) {
            return res.status(404).json({ success: false, message: 'Role not found' });
        }
        
        const { name, color, hoist, position, permissions } = req.body;
        
        const updateOptions = {};
        if (name) updateOptions.name = name;
        if (color !== undefined) updateOptions.color = color;
        if (hoist !== undefined) updateOptions.hoist = hoist;
        if (position !== undefined) updateOptions.position = position;
        if (permissions !== undefined) updateOptions.permissions = permissions;
        
        await role.edit(updateOptions);
        
        res.json({
            success: true,
            message: 'Role updated successfully',
            role: {
                id: role.id,
                name: role.name,
                color: role.color,
                hoist: role.hoist,
                position: role.position,
                permissions: role.permissions.bitfield.toString()
            }
        });
    } catch (error) {
        console.error('Error updating role:', error);
        res.status(500).json({ success: false, message: 'Failed to update role', error: error.message });
    }
});

// API endpoint to delete role
app.delete('/api/guilds/:guildId/roles/:roleId', authenticate, async (req, res) => {
    try {
        const guild = client.guilds.cache.get(req.params.guildId);
        if (!guild) {
            return res.status(404).json({ success: false, message: 'Guild not found' });
        }
        
        const role = guild.roles.cache.get(req.params.roleId);
        if (!role) {
            return res.status(404).json({ success: false, message: 'Role not found' });
        }
        
        await role.delete();
        
        res.json({
            success: true,
            message: 'Role deleted successfully'
        });
    } catch (error) {
        console.error('Error deleting role:', error);
        res.status(500).json({ success: false, message: 'Failed to delete role', error: error.message });
    }
});

// API endpoint to get members
app.get('/api/guilds/:guildId/members', authenticate, async (req, res) => {
    try {
        const guild = client.guilds.cache.get(req.params.guildId);
        if (!guild) {
            return res.status(404).json({ success: false, message: 'Guild not found' });
        }
        
        await guild.members.fetch();
        
        const members = guild.members.cache.map(member => ({
            id: member.id,
            username: member.user.username,
            discriminator: member.user.discriminator,
            nickname: member.nickname,
            avatar: member.user.avatarURL(),
            joinedAt: member.joinedAt,
            roles: member.roles.cache.map(role => role.id)
        }));
        
        res.json(members);
    } catch (error) {
        console.error('Error fetching members:', error);
        res.status(500).json({ success: false, message: 'Failed to fetch members', error: error.message });
    }
});

// API endpoint to kick member
app.post('/api/guilds/:guildId/members/:memberId/kick', authenticate, async (req, res) => {
    try {
        const guild = client.guilds.cache.get(req.params.guildId);
        if (!guild) {
            return res.status(404).json({ success: false, message: 'Guild not found' });
        }
        
        const member = await guild.members.fetch(req.params.memberId);
        if (!member) {
            return res.status(404).json({ success: false, message: 'Member not found' });
        }
        
        const { reason } = req.body;
        
        await member.kick(reason);
        
        res.json({
            success: true,
            message: 'Member kicked successfully'
        });
    } catch (error) {
        console.error('Error kicking member:', error);
        res.status(500).json({ success: false, message: 'Failed to kick member', error: error.message });
    }
});

// API endpoint to ban member
app.post('/api/guilds/:guildId/members/:memberId/ban', authenticate, async (req, res) => {
    try {
        const guild = client.guilds.cache.get(req.params.guildId);
        if (!guild) {
            return res.status(404).json({ success: false, message: 'Guild not found' });
        }
        
        const { reason, deleteMessageDays } = req.body;
        
        await guild.bans.create(req.params.memberId, {
            reason,
            deleteMessageDays: deleteMessageDays || 0
        });
        
        res.json({
            success: true,
            message: 'Member banned successfully'
        });
    } catch (error) {
        console.error('Error banning member:', error);
        res.status(500).json({ success: false, message: 'Failed to ban member', error: error.message });
    }
});

// API endpoint to unban member
app.post('/api/guilds/:guildId/bans/:userId/unban', authenticate, async (req, res) => {
    try {
        const guild = client.guilds.cache.get(req.params.guildId);
        if (!guild) {
            return res.status(404).json({ success: false, message: 'Guild not found' });
        }
        
        const { reason } = req.body;
        
        await guild.bans.remove(req.params.userId, reason);
        
        res.json({
            success: true,
            message: 'Member unbanned successfully'
        });
    } catch (error) {
        console.error('Error unbanning member:', error);
        res.status(500).json({ success: false, message: 'Failed to unban member', error: error.message });
    }
});

// API endpoint to get messages
app.get('/api/channels/:channelId/messages', authenticate, async (req, res) => {
    try {
        const channel = client.channels.cache.get(req.params.channelId);
        if (!channel) {
            return res.status(404).json({ success: false, message: 'Channel not found' });
        }
        
        const limit = parseInt(req.query.limit) || 50;
        const before = req.query.before;
        
        const options = { limit };
        if (before) options.before = before;
        
        const messages = await channel.messages.fetch(options);
        
        const formattedMessages = messages.map(message => ({
            id: message.id,
            content: message.content,
            author: {
                id: message.author.id,
                username: message.author.username,
                discriminator: message.author.discriminator,
                avatar: message.author.avatarURL()
            },
            timestamp: message.createdAt,
            attachments: message.attachments.map(attachment => ({
                id: attachment.id,
                url: attachment.url,
                filename: attachment.filename,
                size: attachment.size
            }))
        }));
        
        res.json(formattedMessages);
    } catch (error) {
        console.error('Error fetching messages:', error);
        res.status(500).json({ success: false, message: 'Failed to fetch messages', error: error.message });
    }
});

// API endpoint to delete message
app.delete('/api/channels/:channelId/messages/:messageId', authenticate, async (req, res) => {
    try {
        const channel = client.channels.cache.get(req.params.channelId);
        if (!channel) {
            return res.status(404).json({ success: false, message: 'Channel not found' });
        }
        
        const message = await channel.messages.fetch(req.params.messageId);
        if (!message) {
            return res.status(404).json({ success: false, message: 'Message not found' });
        }
        
        await message.delete();
        
        res.json({
            success: true,
            message: 'Message deleted successfully'
        });
    } catch (error) {
        console.error('Error deleting message:', error);
        res.status(500).json({ success: false, message: 'Failed to delete message', error: error.message });
    }
});

// API endpoint to bulk delete messages
app.post('/api/channels/:channelId/messages/bulk-delete', authenticate, async (req, res) => {
    try {
        const channel = client.channels.cache.get(req.params.channelId);
        if (!channel) {
            return res.status(404).json({ success: false, message: 'Channel not found' });
        }
        
        const { messageIds } = req.body;
        
        if (!messageIds || !Array.isArray(messageIds) || messageIds.length === 0) {
            return res.status(400).json({ success: false, message: 'Invalid message IDs' });
        }
        
        if (messageIds.length > 100) {
            return res.status(400).json({ success: false, message: 'Cannot delete more than 100 messages at once' });
        }
        
        await channel.bulkDelete(messageIds);
        
        res.json({
            success: true,
            message: 'Messages deleted successfully'
        });
    } catch (error) {
        console.error('Error bulk deleting messages:', error);
        res.status(500).json({ success: false, message: 'Failed to delete messages', error: error.message });
    }
});

// API endpoint to send message
app.post('/api/channels/:channelId/messages', authenticate, async (req, res) => {
    try {
        const channel = client.channels.cache.get(req.params.channelId);
        if (!channel) {
            return res.status(404).json({ success: false, message: 'Channel not found' });
        }
        
        const { content, embed } = req.body;
        
        let messageOptions = {};
        if (content) messageOptions.content = content;
        if (embed) messageOptions.embeds = [embed];
        
        const message = await channel.send(messageOptions);
        
        res.json({
            success: true,
            message: 'Message sent successfully',
            messageData: {
                id: message.id,
                content: message.content,
                timestamp: message.createdAt
            }
        });
    } catch (error) {
        console.error('Error sending message:', error);
        res.status(500).json({ success: false, message: 'Failed to send message', error: error.message });
    }
});

// API endpoint to get guild settings
app.get('/api/guilds/:guildId/settings', authenticate, (req, res) => {
    const guild = client.guilds.cache.get(req.params.guildId);
    if (!guild) {
        return res.status(404).json({ success: false, message: 'Guild not found' });
    }
    
    res.json({
        name: guild.name,
        icon: guild.iconURL(),
        region: guild.preferredLocale,
        verificationLevel: guild.verificationLevel,
        explicitContentFilter: guild.explicitContentFilter,
        defaultMessageNotifications: guild.defaultMessageNotifications
    });
});

// API endpoint to update guild settings
app.patch('/api/guilds/:guildId/settings', authenticate, async (req, res) => {
    try {
        const guild = client.guilds.cache.get(req.params.guildId);
        if (!guild) {
            return res.status(404).json({ success: false, message: 'Guild not found' });
        }
        
        const { name, region, verificationLevel, explicitContentFilter, defaultMessageNotifications } = req.body;
        
        const updateOptions = {};
        if (name) updateOptions.name = name;
        if (region) updateOptions.preferredLocale = region;
        if (verificationLevel !== undefined) updateOptions.verificationLevel = verificationLevel;
        if (explicitContentFilter !== undefined) updateOptions.explicitContentFilter = explicitContentFilter;
        if (defaultMessageNotifications !== undefined) updateOptions.defaultMessageNotifications = defaultMessageNotifications;
        
        await guild.edit(updateOptions);
        
        res.json({
            success: true,
            message: 'Guild settings updated successfully'
        });
    } catch (error) {
        console.error('Error updating guild settings:', error);
        res.status(500).json({ success: false, message: 'Failed to update guild settings', error: error.message });
    }
});

// Start the web server
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`Web server running on port ${PORT}`);
});

// Handle Discord errors
client.on('error', console.error);
client.on('warn', console.warn);

// Process exit handler
process.on('exit', () => {
    console.log('Bot shutting down');
});

// Handle unhandled promise rejections
process.on('unhandledRejection', error => {
    console.error('Unhandled promise rejection:', error);
});
