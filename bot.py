import discord
from groq import Groq
import os
import json
import urllib.request
import urllib.parse
import requests
from bs4 import BeautifulSoup
from collections import deque # Added for chat history

# --- CONFIGURATION ---
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
YOUR_USER_ID = 123456789012345678  # Replace with your ID
MODEL_NAME = "llama-3.3-70b-versatile"
SEARXNG_URL = "http://100.113.140.50:8888" # Replace with your IP

# Initialize Chat History (remembers the last 20 messages)
chat_history = deque(maxlen=20)
# ---------------------

groq_client = Groq(api_key=GROQ_API_KEY)
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# --- Tool 1: Web Search ---
def search_web(query: str) -> str:
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
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        for script in soup(["script", "style", "nav", "footer", "header"]):
            script.extract()
            
        text = soup.get_text(separator=' ', strip=True)
        if len(text) > 15000:
            text = text[:15000] + "... [Content Truncated]"
        return text
    except Exception as e:
        return f"Error reading webpage: {e}"

# --- The Router Function ---
def analyze_intent(prompt: str, history: list):
    """Uses a fast LLM to decide if a tool is needed, using recent history for context."""
    
    # Format the last few messages for the router to understand the context
    history_text = "\n".join([f"{msg['role'].capitalize()}: {msg['content']}" for msg in history[-4:]])
    
    router_prompt = f"""
    You are an intent analyzer. Decide if the user needs to search the web, read a specific URL, or just chat.
    Use the recent chat history to understand references like 'he', 'it', or 'there'.
    Output ONLY a valid JSON object in this format: {{"action": "chat"}} OR {{"action": "search_web", "query": "optimized search term"}} OR {{"action": "read_webpage", "url": "http://..."}}
    
    Recent Chat History:
    {history_text}
    
    User Prompt: {prompt}
    """
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": router_prompt}],
            response_format={"type": "json_object"},
            temperature=0
        )
        return json.loads(response.choices[0].message.content)
    except Exception:
        return {"action": "chat"}

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

    # Optional: Command to clear the bot's memory manually
    if prompt.lower() == "!clear":
        chat_history.clear()
        await message.reply("Chat history cleared!", mention_author=False)
        return

    async with message.channel.typing():
        try:
            # 1. Route the Intent manually, passing the current chat history
            intent = analyze_intent(prompt, list(chat_history))
            tool_context = ""
            
            # 2. Execute tools if needed
            if intent.get("action") == "search_web":
                tool_context = search_web(intent.get("query"))
            elif intent.get("action") == "read_webpage":
                tool_context = read_webpage(intent.get("url"))
                
            # 3. Build the system prompt
            system_instruction = "You are a helpful and intelligent assistant."
            if tool_context:
                # We inject the tool context into the system prompt, NOT the chat history, 
                # so the bot doesn't memorize thousands of words of web-scraping text.
                system_instruction += f"\n\nUse the following live data to answer the user's request:\n{tool_context}"
                
            # 4. Assemble the final messages array: System -> History -> Current Prompt
            messages = [{"role": "system", "content": system_instruction}]
            messages.extend(list(chat_history))
            messages.append({"role": "user", "content": prompt})
            
            # 5. Generate the final answer
            final_response = groq_client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                temperature=0.7
            )
            
            final_text = final_response.choices[0].message.content
            
            # 6. Save this interaction to the chat history memory
            chat_history.append({"role": "user", "content": prompt})
            chat_history.append({"role": "assistant", "content": final_text})
            
            if final_text:
                for i in range(0, len(final_text), 2000):
                    await message.reply(final_text[i:i+2000], mention_author=False)

        except Exception as e:
            await message.channel.send(f"An error occurred: {e}")

client.run(DISCORD_TOKEN)