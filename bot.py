import discord
from groq import Groq

# --- CONFIGURATION ---
DISCORD_TOKEN = "YOUR_DISCORD_BOT_TOKEN_HERE"
GROQ_API_KEY = "YOUR_GROQ_API_KEY_HERE"
YOUR_USER_ID = 123456789012345678  # Replace with your actual Discord User ID
MODEL_NAME = "llama-3.3-70b-versatile" # Choose your preferred Groq model
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