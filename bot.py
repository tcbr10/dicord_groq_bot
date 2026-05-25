import discord
from groq import Groq
import os
import json
import urllib.request
import urllib.parse

# --- CONFIGURATION ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
YOUR_USER_ID = 123456789012345678
MODEL_NAME = "llama-3.3-70b-versatile"
# Change this IP to your server's local IP address if not running on the exact same network bridge
SEARXNG_URL = "http://127.0.0.1:8888" 
# ---------------------

groq_client = Groq(api_key=GROQ_API_KEY)
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# --- 1. Define the SearXNG Search Function ---
def search_web(query: str) -> str:
    """Searches the live web using your self-hosted SearXNG instance."""
    try:
        url = f"{SEARXNG_URL}/search?q={urllib.parse.quote(query)}&format=json"
        
        req = urllib.request.Request(url, headers={'User-Agent': 'GroqDiscordBot/1.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            
        results = data.get('results', [])
        if not results:
            return "No results found on the web."
            
        # Format the top 3 results
        formatted_results = "Web Search Results:\n\n"
        for i, res in enumerate(results[:3]):
            title = res.get('title', 'No Title')
            content = res.get('content', 'No Content')
            link = res.get('url', 'No Link')
            formatted_results += f"{i+1}. {title}\nSnippet: {content}\nSource: {link}\n\n"
            
        return formatted_results
    except Exception as e:
        return f"Error connecting to SearXNG: {e}"

# --- 2. Tell Groq about the Tool ---
tools = [
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Searches the live internet for up-to-date news, facts, and general information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to look up on the web.",
                    }
                },
                "required": ["query"],
            },
        },
    }
]

@client.event
async def on_ready():
    print(f'Logged in as {client.user}!')

@client.event
async def on_message(message):
    if message.author.bot:
        return

    prompt = message.content.strip()
    if not prompt:
        return

    async with message.channel.typing():
        try:
            messages = [
                {
                    "role": "system", 
                    "content": "You are a helpful assistant. Use the tools provided when necessary. NEVER use XML or HTML tags like <function> or <tool_call> in your responses."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ]

            
            response = groq_client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                parallel_tool_calls=False # <-- THIS IS THE CRITICAL FIX
            )

            
            response_message = response.choices[0].message
            
            if response_message.tool_calls:
                messages.append(response_message)
                for tool_call in response_message.tool_calls:
                    if tool_call.function.name == "search_web":
                        function_args = json.loads(tool_call.function.arguments)
                        search_query = function_args.get("query")
                        
                        search_results = search_web(search_query)
                        
                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": "search_web",
                            "content": search_results,
                        })
                
                final_response = groq_client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages
                )
                final_text = final_response.choices[0].message.content
            else:
                final_text = response_message.content
            
            for i in range(0, len(final_text), 2000):
                await message.reply(final_text[i:i+2000], mention_author=False)

        except Exception as e:
            await message.channel.send(f"An error occurred: {e}")

client.run(DISCORD_TOKEN)