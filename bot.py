import discord
from groq import Groq
import os
import json
from duckduckgo_search import DDGS

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

# --- 1. Define the actual Python function for searching ---
def search_duckduckgo(query: str) -> str:
    """Searches the web using DuckDuckGo and returns the results."""
    try:
        results = DDGS().text(query, max_results=3)
        if not results:
            return "No results found."
        
        # Format the results into a string for the AI to read
        formatted_results = ""
        for r in results:
            formatted_results += f"Title: {r['title']}\nSummary: {r['body']}\nURL: {r['href']}\n\n"
        return formatted_results
    except Exception as e:
        return f"Error performing search: {e}"

# --- 2. Tell Groq what tools are available ---
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
                        "description": "The search query to look up on the internet.",
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
            # Step 1: Send the user's prompt to Groq, providing the search tool
            messages = [{"role": "user", "content": prompt}]
            
            response = groq_client.chat.completions.create(
                model=MODEL_NAME,
                messages=messages,
                tools=tools,
                tool_choice="auto", # Lets the AI decide if it needs to search
            )
            
            response_message = response.choices[0].message
            
            # Step 2: Check if Groq decided to use the search tool
            if response_message.tool_calls:
                # Add the AI's tool request to the message history
                messages.append(response_message)
                
                # Execute the search for each tool call
                for tool_call in response_message.tool_calls:
                    if tool_call.function.name == "search_duckduckgo":
                        # Get the search query the AI generated
                        function_args = json.loads(tool_call.function.arguments)
                        search_query = function_args.get("query")
                        
                        # Run our python search function
                        search_results = search_duckduckgo(search_query)
                        
                        # Step 3: Send the search results back to Groq
                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": "search_duckduckgo",
                            "content": search_results,
                        })
                
                # Step 4: Ask Groq to generate a final answer using the search results
                final_response = groq_client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages
                )
                final_text = final_response.choices[0].message.content
            else:
                # If no tool was needed (like for "Hello!"), just use the standard response
                final_text = response_message.content
            
            # Send the final response to Discord
            for i in range(0, len(final_text), 2000):
                await message.reply(final_text[i:i+2000], mention_author=False)

        except Exception as e:
            await message.channel.send(f"An error occurred: {e}")

client.run(DISCORD_TOKEN)