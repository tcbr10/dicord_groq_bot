import discord
from groq import Groq
import os
import json
import urllib.request
import urllib.parse
import requests
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
YOUR_USER_ID = 123456789012345678  # Replace with your actual Discord User ID
MODEL_NAME = "llama-3.3-70b-versatile"

# Ensure this points to your SearXNG container! 
# (e.g., http://searxng:8080 if they are on the same Docker network)
SEARXNG_URL = "http://100.113.140.50:8888" 
# ---------------------

# Initialize Clients
groq_client = Groq(api_key=GROQ_API_KEY)
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# --- Tool 1: Web Search ---
def search_web(query: str) -> str:
    """Searches the live internet using your self-hosted SearXNG instance."""
    try:
        url = f"{SEARXNG_URL}/search?q={urllib.parse.quote(query)}&format=json"
        req = urllib.request.Request(url, headers={'User-Agent': 'GroqDiscordBot/1.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            
        results = data.get('results', [])
        if not results:
            return "No results found on the web."
            
        formatted_results = "Web Search Results:\n\n"
        for i, res in enumerate(results[:3]):
            title = res.get('title', 'No Title')
            content = res.get('content', 'No Content')
            link = res.get('url', 'No Link')
            formatted_results += f"{i+1}. {title}\nSnippet: {content}\nSource: {link}\n\n"
            
        return formatted_results
    except Exception as e:
        return f"Error connecting to SearXNG: {e}"

# --- Tool 2: Web Scraper ---
def read_webpage(url: str) -> str:
    """Fetches a webpage and extracts the readable text."""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Strip out useless backend code
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.extract()
            
        text = soup.get_text(separator=' ', strip=True)
        
        # Prevent the AI from crashing due to token limits on massive sites
        if len(text) > 15000:
            text = text[:15000] + "... [Content Truncated]"
            
        return text
    except Exception as e:
        return f"Error reading webpage: {e}"

# --- Tool Definitions for Groq ---
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
    },
    {
        "type": "function",
        "function": {
            "name": "read_webpage",
            "description": "Opens a specific URL and reads its full text content. Use this to read the full article from a search result link.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The full URL of the webpage to read.",
                    }
                },
                "required": ["url"],
            },
        },
    }
]

@client.event
async def on_ready():
    print(f'Logged in as {client.user}!')

@client.event
async def on_message(message):
    # Ignore other bots and anyone who isn't you
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
                    "content": "You are a helpful assistant with internet access. If you need details, use the search_web tool. If you need to read a full article, use the read_webpage tool."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ]
            
            # Step 1: Ask Groq
            response = groq_client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                parallel_tool_calls=False
            )
            
            # This is the variable that was missing/throwing the error!
            response_message = response.choices[0].message
            
            # Step 2: Handle Tool Usage
            if response_message.tool_calls:
                messages.append(response_message)
                
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    if function_name == "search_web":
                        search_query = function_args.get("query")
                        tool_results = search_web(search_query)
                    elif function_name == "read_webpage":
                        url_to_read = function_args.get("url")
                        tool_results = read_webpage(url_to_read)
                    else:
                        tool_results = "Error: Unknown function."
                        
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": tool_results,
                    })
                
                # Step 3: Get final answer after tool usage
                final_response = groq_client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages
                )
                final_text = final_response.choices[0].message.content
            else:
                # If no tool was used, just reply normally
                final_text = response_message.content
            
            # Send to Discord (chunking if it exceeds Discord's 2000 character limit)
            if final_text:
                for i in range(0, len(final_text), 2000):
                    await message.reply(final_text[i:i+2000], mention_author=False)

        except Exception as e:
            await message.channel.send(f"An error occurred: {e}")

client.run(DISCORD_TOKEN)