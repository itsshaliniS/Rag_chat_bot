from google import genai
from google.genai import types

import config

_client = None


def get_client():
    global _client
    if _client is None:
        if not config.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY is missing. Add it to your .env file.")
        _client = genai.Client(api_key=config.GOOGLE_API_KEY)
    return _client


def embed_text(text, task_type='RETRIEVAL_DOCUMENT'):
    # print("generating embedding for text chunk...")
    client = get_client()
    result = client.models.embed_content(
        model=config.EMBEDDING_MODEL,
        contents=text,
        config=types.EmbedContentConfig(task_type=task_type),
    )
    return result.embeddings[0].values


def generate_answer(prompt):
    client = get_client()
    try:
        print("sending prompt to gemini client...")
        response = client.models.generate_content(
            model=config.CHAT_MODEL,
            contents=prompt,
        )
        return response.text
    except Exception as e:
        print("Error calling Gemini API:", e)
        if 'RESOURCE_EXHAUSTED' in str(e) or '429' in str(e):
            raise RuntimeError(
                "Gemini limit reached. Try again later or use another API key."
            )
        raise

