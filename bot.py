import discord
from groq import Groq
import os

# --- CONFIGURATION ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
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

    # Grab the text you typed
    prompt = message.content.strip()
    
    # Don't respond to empty messages (like if you just send an image)
    if not prompt:
        return

    # Show a "typing..." indicator in Discord while waiting for Groq
    async with message.channel.typing():
        try:
            # Call Groq API
            chat_completion = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=MODEL_NAME,
            )
            
            # Send the response back to Discord using the reply function
            # mention_author=False means it won't ping you every time it replies
            response_text = chat_completion.choices[0].message.content
            
            # Discord messages have a 2000 char limit, chunk if necessary
            for i in range(0, len(response_text), 2000):
                await message.reply(response_text[i:i+2000], mention_author=False)

        except Exception as e:
            await message.channel.send(f"An error occurred: {e}")

# Start the bot
client.run(DISCORD_TOKEN)