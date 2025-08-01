# config.py

"""
Central configuration file for the in5 startup scraper project.
"""

# The URL of the in5 startup directory to be scraped.
BASE_URL = "https://infive.ae/setup/directory/"

# The name of the output file where the scraped data will be saved.
OUTPUT_CSV_FILE = "infive_startups.csv"

# --- Scraping Parameters ---

# Set to True to run the browser in headless mode (without a UI).
# Set to False for debugging to see the browser actions.
HEADLESS_MODE = True

# Timeout in milliseconds for page navigation.
PAGE_TIMEOUT = 60000

# Time in seconds to wait between scrolls to allow content to load.
SCROLL_DELAY = 2
