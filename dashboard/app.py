from flask import render_template, jsonify, request
import logging
import asyncio
import discord
import io

# This file no longer creates the Flask app or SocketIO instance.
# It only defines the routes and handlers on the objects passed from bot.py.

# In-memory mapping of a client's session ID to the channel they are watching
client_channels = {}

def run_dashboard(bot, loop, app, socketio):
    """Configures and runs the Flask web server and SocketIO handlers."""
    
    app.config['bot'] = bot
    app.config['loop'] = loop

    # --- Socket.IO Handlers for real-time communication ---
    @socketio.on('connect')
    def handle_connect():
        logging.info(f'[Dashboard] Client connected: {request.sid}')

    @socketio.on('disconnect')
    def handle_disconnect():
        logging.info(f'[Dashboard] Client disconnected: {request.sid}')
        if request.sid in client_channels:
            del client_channels[request.sid]

    @socketio.on('view_channel')
    def handle_view_channel(data):
        """Registers that a client is watching a specific channel."""
        channel_id = data.get('channel_id')
        logging.info(f"[Dashboard] Received 'view_channel' event with data: {data}")
        if channel_id:
            client_channels[request.sid] = int(channel_id)
            logging.info(f"[Dashboard] Client {request.sid} is now viewing channel {channel_id}. Current watchers: {client_channels}")
        elif request.sid in client_channels:
            old_channel = client_channels.pop(request.sid)
            logging.info(f"[Dashboard] Client {request.sid} stopped viewing channel {old_channel}. Current watchers: {client_channels}")

    # --- Bot Event Listener to forward messages to the dashboard ---
    async def on_message_dashboard(message):
        if message.author.bot or not message.guild:
            return

        logging.info(f"[Dashboard] on_message event in channel {message.channel.id}. Watchers: {client_channels}")

        is_watched = any(channel_id == message.channel.id for channel_id in client_channels.values())
        if not is_watched:
            return

        logging.info(f"[Dashboard] Channel {message.channel.id} is being watched. Preparing to emit message.")

        message_data = {
            'author': message.author.name,
            'avatar_url': str(message.author.display_avatar.url),
            'content': message.content,
            'timestamp': message.created_at.strftime('%H:%M'),
            'channel_id': message.channel.id
        }
        
        emitted_to = []
        for sid, channel_id in client_channels.items():
            if message.channel.id == channel_id:
                socketio.emit('new_message', message_data, to=sid)
                emitted_to.append(sid)
        
        if emitted_to:
            logging.info(f"[Dashboard] Emitted 'new_message' to SIDs: {emitted_to}")

    bot.add_listener(on_message_dashboard, 'on_message')

    # --- Flask Routes ---
    @app.route('/')
    def index():
        """Renders the main dashboard page."""
        bot = app.config['bot']
        return render_template('index.html', bot=bot)

    @app.route('/api/stats')
    def api_stats():
        """Provides live stats as a JSON object for the frontend to fetch."""
        bot = app.config['bot']
        if not bot.is_ready():
            return jsonify({"status": "Bot is not ready"}), 503

        guilds = bot.guilds
        total_users = sum(guild.member_count for guild in guilds)

        return jsonify({
            "status": "Online" if bot.is_ready() else "Offline",
            "latency": f"{bot.latency * 1000:.2f}",
            "server_count": len(guilds),
            "user_count": total_users
        })

    @app.route('/api/servers')
    def api_servers():
        """Provides a list of servers and their text channels."""
        bot = app.config['bot']
        if not bot.is_ready():
            return jsonify({}), 503
        
        server_data = []
        for guild in bot.guilds:
            channels = [{'id': str(c.id), 'name': c.name} for c in guild.text_channels]
            server_data.append({'id': str(guild.id), 'name': guild.name, 'channels': channels})
        
        return jsonify(server_data)

    @app.route('/api/messages/<int:channel_id>')
    def api_messages(channel_id):
        """Provides recent message history for a channel."""
        bot = app.config['bot']
        loop = app.config['loop']
        if not bot.is_ready():
            return jsonify([]), 503
        
        channel = bot.get_channel(channel_id)
        if not channel:
            return jsonify([]), 404

        async def get_history():
            messages = []
            async for msg in channel.history(limit=50):
                messages.append({
                    'author': msg.author.name,
                    'avatar_url': str(msg.author.display_avatar.url),
                    'content': msg.content,
                    'timestamp': msg.created_at.strftime('%H:%M')
                })
            messages.reverse()
            return messages

        future = asyncio.run_coroutine_threadsafe(get_history(), loop)
        messages = future.result()
        return jsonify(messages)

    @app.route('/api/send_message', methods=['POST'])
    def send_message():
        """Receives message data from the dashboard and tells the bot to send it."""
        bot = app.config['bot']
        loop = app.config['loop']
        if not bot.is_ready():
            return jsonify({"status": "error", "message": "Bot not ready"}), 503

        channel_id = request.form.get('channel_id')
        message_content = request.form.get('message')
        image_file = request.files.get('image')

        if not channel_id:
            return jsonify({"status": "error", "message": "Missing channel ID"}), 400
        
        if not message_content and not image_file:
            return jsonify({"status": "error", "message": "Message and image cannot both be empty"}), 400

        channel = bot.get_channel(int(channel_id))
        if not channel:
            return jsonify({"status": "error", "message": "Channel not found"}), 404

        async def send_message_async():
            try:
                discord_file = None
                if image_file:
                    image_data = io.BytesIO(image_file.read())
                    discord_file = discord.File(fp=image_data, filename=image_file.filename)

                await channel.send(content=message_content if message_content else None, file=discord_file)
            except Exception as e:
                logging.error(f"Error sending message from dashboard: {e}")

        future = asyncio.run_coroutine_threadsafe(send_message_async(), loop)
        future.result()

        return jsonify({"status": "success"})

    # The server is now run from the thread in bot.py
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)