import discord
from groq import Groq
import os
import json
import urllib.request
from html.parser import HTMLParser

# --- CONFIGURATION ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
YOUR_USER_ID = 123456789012345678  # Keep your actual Discord User ID here
MODEL_NAME = "llama-3.3-70b-versatile"
# ---------------------

# Initialize Clients
groq_client = Groq(api_key=GROQ_API_KEY)
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# --- 1. Define the Native Python function for searching ---
class DDGParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self.in_snippet = False
        self.current_snippet = ""
        self.result_count = 0

    def handle_starttag(self, tag, attrs):
        if tag == "a" and self.result_count < 3:
            for attr, value in attrs:
                if attr == "class" and "result-snippet" in value:
                    self.in_snippet = True

    def handle_data(self, data):
        if self.in_snippet:
            self.current_snippet += data.strip() + " "

    def handle_endtag(self, tag):
        if tag == "a" and self.in_snippet:
            self.in_snippet = False
            self.results.append(self.current_snippet.strip())
            self.current_snippet = ""
            self.result_count += 1

def search_duckduckgo(query: str) -> str:
    """Searches the web using native Python to avoid Docker dependency crashes."""
    try:
        # Format the query for the URL
        url_query = urllib.parse.quote(query)
        url = f"https://html.duckduckgo.com/html/?q={url_query}"
        
        # We must use a User-Agent so DuckDuckGo doesn't block the request
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        
        with urllib.request.urlopen(req) as response:
            html = response.read().decode('utf-8')
            
        parser = DDGParser()
        parser.feed(html)
        
        if not parser.results:
            return "No results found."
            
        # Format results for the AI
        formatted = "Search Results:\n"
        for idx, res in enumerate(parser.results):
            formatted += f"{idx+1}. {res}\n"
            
        return formatted
    except Exception as e:
        return f"Error performing search: {e}"

# --- 2. Tell Groq about the tool ---
tools = [
    {
        "type": "function",
        "function": {
            "name": "search_duckduckgo",
            "description": "Searches the web for recent, real-time, or unknown information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to look up.",
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
    
    prompt = message.content.strip()
    if not prompt:
        return

    async with message.channel.typing():
        try:
            messages = [{"role": "user", "content": prompt}]
            
            response = groq_client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )
            
            response_message = response.choices[0].message
            
            if response_message.tool_calls:
                messages.append(response_message)
                for tool_call in response_message.tool_calls:
                    if tool_call.function.name == "search_duckduckgo":
                        function_args = json.loads(tool_call.function.arguments)
                        search_query = function_args.get("query")
                        
                        search_results = search_duckduckgo(search_query)
                        
                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": "search_duckduckgo",
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