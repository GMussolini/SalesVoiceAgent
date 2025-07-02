import openai
import asyncio
from app import config, prompts


openai.api_key = config.OPENAI_API_KEY
MODEL = "gpt-4o-mini"

async def generate_reply(history: list[str]) -> str:
    """history alterna [user, assistant, user, …]"""
    messages = [
        {"role": "system", "content": prompts.BASE_PROMPT}
    ]
    for i, t in enumerate(history):
        messages.append({"role": "user" if i % 2 == 0 else "assistant", "content": t})

    resp = await openai.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.4,
        max_tokens=160,
        stream=True,
    )
    return resp.choices[0].message.content.strip()