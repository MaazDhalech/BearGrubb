from __future__ import annotations

import os

try:
    from dotenv import load_dotenv
except ImportError:  # Dependencies are installed by requirements.txt in real local use.
    load_dotenv = None

if load_dotenv:
    load_dotenv()

DINING_HALLS = {
    "Cafe 3": "cafe3",
    "Crossroads": "crossroads",
    "Foothill": "foothill",
    "Clark Kerr": "clark-kerr",
}

DINING_MENU_ENDPOINT = "https://dining.berkeley.edu/wp-json/bc-dining/v1/dining-menu"

COLLECTION_NAME = "beargrub_menu"
CHROMA_PATH = "./chroma_db"
CACHE_PATH = "./classification_cache.json"
MENU_DATA_PATH = "./menu_data"

OPENAI_MODEL = "gpt-4o-mini"
EMBEDDING_MODEL = "text-embedding-3-small"

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
POSTHOG_API_KEY = os.getenv("POSTHOG_API_KEY")
S3_BUCKET = os.getenv("S3_BUCKET", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

REQUEST_TIMEOUT_SECONDS = 15

DEBUG = os.getenv("BEARGRUB_DEBUG", "").lower() in ("1", "true")
