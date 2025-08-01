# config.py

"""
Central configuration file for the in5 startup scraper project.
"""

# The URL of the in5 startup directory to be scraped.
BASE_URL = "https://infive.ae/setup/directory/"

# --- NEW: Output Directory and Filename ---
# Directory where the output CSV files will be saved.
OUTPUT_DIR = "scraped_data"
# Base name for the output files. The letter will be appended.
OUTPUT_FILENAME_BASE = "infive_startups"


# --- Scraping Parameters ---

# Set to True to run the browser in headless mode (without a UI).
# Set to False for debugging to see the browser actions.
HEADLESS_MODE = False

# Timeout in milliseconds for page navigation.
PAGE_TIMEOUT = 60000

# Time in seconds to wait between clicks or scrolls.
ACTION_DELAY = 2.5

# --- NEW: Characters to Scrape ---
# The list of characters to iterate through when using the --all flag.
SCRAPE_CHARACTERS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z']
