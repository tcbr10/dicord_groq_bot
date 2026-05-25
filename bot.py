import discord
from groq import Groq
import os
import json
import urllib.request
import urllib.parse
import re
import requests
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
YOUR_USER_ID = 123456789012345678
MODEL_NAME = "llama-3.3-70b-versatile"
# Change this IP to your server's local IP address if not running on the exact same network bridge
SEARXNG_URL = "http://100.113.140.50:8888" 
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
    
# --- Define the Webpage Reader Function ---
def read_webpage(url: str) -> str:
    """Fetches a webpage and extracts the readable text."""
    try:
        # Use a standard User-Agent so websites don't block the request
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parse the HTML and extract text
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Remove javascript and stylesheet code
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.extract()
            
        text = soup.get_text(separator=' ', strip=True)
        
        # Truncate the text to 15,000 characters so we don't exceed Groq's token limits
        if len(text) > 15000:
            text = text[:15000] + "... [Content Truncated]"
            
        return text
    except Exception as e:
        return f"Error reading webpage: {e}"

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
    },
    {
        "type": "function",
        "function": {
            "name": "read_webpage",
            "description": "Opens a specific URL and reads its full text content. Use this when the search snippet does not contain enough information.",
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
    if message.author.bot:
        return

    prompt = message.content.strip()
    if not prompt:
        return

    async with message.channel.typing():
        try:
            # We add a strong system prompt to guide the output
            messages = [
                {
                    "role": "system", 
                    "content": "You are a helpful assistant. If you need to search the web, output exactly: <function=search_web>{\"query\": \"your search query\"}</function>"
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ]
            
            # Note: We must pass 'tools' so the model knows it exists, 
            # even though we are going to manually parse its text output.
            response = groq_client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )
            
            response_text = response.choices[0].message.content or ""
            
            # Step 1: Check if the model output the <function=...> tag natively
            if "function=search_web" in response_text:
                # Extract the JSON part between the tags
                match = re.search(r'<function=search_web\s*({.*?})\s*(?:</function>)?', response_text)
                if match:
                    json_str = match.group(1)
                    try:
                        function_args = json.loads(json_str)
                        search_query = function_args.get("query")
                        
                        # Execute the SearXNG search
                        search_results = search_web(search_query)
                        
                        # Step 2: Feed the results back to the model
                        messages.append({
                            "role": "assistant",
                            "content": response_text # Pass back exactly what it wrote
                        })
                        messages.append({
                            "role": "user",
                            "content": f"Search Results for '{search_query}':\n{search_results}\n\nBased on these results, please answer my original question."
                        })
                        
                        # Get the final answer
                        final_response = groq_client.chat.completions.create(
                            model=MODEL_NAME,
                            messages=messages
                        )
                        response_text = final_response.choices[0].message.content
                    except json.JSONDecodeError:
                        response_text = "Sorry, I encountered an error parsing the search query."
            
            # If it used the standard tool_calls array instead (just in case Groq fixes it)
            elif response.choices[0].message.tool_calls:
                messages.append(response.choices[0].message)
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    
                    # Decide which tool to run
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

                final_response = groq_client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages
                )
                response_text = final_response.choices[0].message.content

            # Step 3: Send the final response to Discord
            for i in range(0, len(response_text), 2000):
                await message.reply(response_text[i:i+2000], mention_author=False)

        except Exception as e:
            await message.channel.send(f"An error occurred: {e}")

client.run(DISCORD_TOKEN)