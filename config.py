# config.py

"""
Central configuration file for the in5 startup scraper project.
"""

# The URL of the in5 startup directory to be scraped.
BASE_URL = "https://infive.ae/setup/directory/"

# --- Output Directory and Filename ---
# Directory where the output CSV files will be saved.
OUTPUT_DIR = "scraped_data"
# Base name for the output files. The letter will be appended.
OUTPUT_FILENAME_BASE = "infive_startups"


# --- Scraping Parameters ---

# Set to True to run the browser in headless mode (without a UI).
# Set to False for debugging to see the browser actions.
HEADLESS_MODE = True

# Timeout in milliseconds for page navigation.
PAGE_TIMEOUT = 60000

# Time in seconds to wait between clicks or scrolls.
ACTION_DELAY = 2.5

# --- Concurrency Settings ---
# The maximum number of concurrent asyncio tasks to run for web scraping.
MAX_CONCURRENT_TASKS = 4
# --- NEW: The maximum number of concurrent workers for processing and app scraping. ---
MAX_PROCESSING_WORKERS = 8


# --- Characters to Scrape ---
# The list of characters to iterate through when using the --all flag.
SCRAPE_CHARACTERS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z']

# --- App Scraping Settings ---
# The number of app results to check per store for each company.
NO_OF_APPS_TO_SCRAPE = 1

# --- Vector Store Settings ---
# The path to the local ChromaDB database directory.
CHROMA_DB_PATH = "chroma_db"
# The name of the collection to store the vectorized data.
CHROMA_COLLECTION_NAME = "in5_startups"
# The name of the sentence transformer model to use for embeddings.
EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"
