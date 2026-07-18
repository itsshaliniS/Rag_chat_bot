import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
DB_FOLDER = os.path.join(BASE_DIR, "database")

ALLOWED_EXTENSIONS = {"pdf", "txt"}
MAX_FILE_SIZE_MB = 20
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

CHUNK_SIZE_WORDS = 200
CHUNK_OVERLAP_WORDS = 30
TOP_K_RESULTS = 5

EMBEDDING_MODEL = "gemini-embedding-001"
CHAT_MODEL = "gemini-3.5-flash"

COLLECTION_NAME = "documents"

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-this")