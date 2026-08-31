import os
from dotenv import load_dotenv
load_dotenv()

import google.generativeai as genai

API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=API_KEY)

print("Listing models...")
try:
    models = list(genai.list_models())
    for m in models:
        print(f"- {m.name} ({m.display_name})")
        print(f"  Supported methods: {m.supported_generation_methods}")
except Exception as e:
    print(f"Error: {e}")
