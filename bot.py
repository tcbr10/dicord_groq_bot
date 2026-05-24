import discord
from groq import Groq
import os

# --- CONFIGURATION (Pulls from Portainer ENV Variables) ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# You can either hardcode this or pass it as an ENV variable too
YOUR_USER_ID = 123456789012345678  
MODEL_NAME = "llama-3.3-70b-versatile"
# ---------------------

# Initialize Groq Client
groq_client = Groq(api_key=GROQ_API_KEY)

# Initialize Discord Client with message intents
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Logged in as {client.user}!')

@client.event
async def on_message(message):
    # Ignore messages sent by the bot itself
    if message.author == client.user:
        return

    # Only respond if the bot is mentioned
    if client.user.mentioned_in(message):
        
        # Remove the bot's mention from the prompt text
        prompt = message.content.replace(f'<@{client.user.id}>', '').strip()
        
        if not prompt:
            await message.channel.send("What's up?")
            return

        # Show a "typing" indicator in Discord while waiting for Groq
        async with message.channel.typing():
            try:
                # Call Groq API
                chat_completion = groq_client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model=MODEL_NAME,
                )
                
                # Send the response back to Discord
                response_text = chat_completion.choices[0].message.content
                
                # Discord messages have a 2000 char limit, so we chunk it if necessary
                for i in range(0, len(response_text), 2000):
                    await message.channel.send(response_text[i:i+2000])

            except Exception as e:
                await message.channel.send(f"An error occurred: {e}")

# Start the bot
client.run(DISCORD_TOKEN)