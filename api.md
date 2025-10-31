Python
Let's make a direct request to the Chutes API using Python.

Need an API token?
Get one here

For this example, we'll use the aiohttps and asyncio libraries. So we'll need to install them. It's recommended to set up a Python virtual environment first if you don't already have one.

bash


pip install aiohttp asyncio
Once you're all set up you can run the following code to generate a 250 word story with DeepSeek R1. Make sure you have your API token ready, enough credits, and that the Chute is currently available.

python


import aiohttp
import asyncio
import json

async def invoke_chute():
	api_token = "$CHUTES_API_TOKEN"  # Replace with your actual API token

	headers = {
		"Authorization": "Bearer " + api_token,
		"Content-Type": "application/json"
	}
	
	body =     {
      "model": "deepseek-ai/DeepSeek-V3.1",
      "messages": [
        {
          "role": "user",
          "content": "Tell me a 250 word story."
        }
      ],
      "stream": True,
      "max_tokens": 1024,
      "temperature": 0.7
    }

	async with aiohttp.ClientSession() as session:
		async with session.post(
			"https://llm.chutes.ai/v1/chat/completions", 
			headers=headers,
			json=body
		) as response:
			async for line in response.content:
				line = line.decode("utf-8").strip()
				if line.startswith("data: "):
					data = line[6:]
					if data == "[DONE]":
						break
					try:
						chunk = data.strip()
						if chunk:
							print(chunk)
					except Exception as e:
						print(f"Error parsing chunk: {e}")

asyncio.run(invoke_chute())