import os
from dotenv import load_dotenv
from google.adk.models.google_llm import Gemini
from google.genai import types as genai_types

load_dotenv()
if not os.getenv("GOOGLE_API_KEY"):
    raise ValueError("GOOGLE_API_KEY not found in .env file.")

retry_config = genai_types.HttpRetryOptions(attempts=5)
worker_model = Gemini(model="gemini-2.5-flash", retry_options=retry_config)
critic_model = Gemini(model="gemini-2.5-pro", retry_options=retry_config)