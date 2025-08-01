# infive_scraper.py

"""
This module contains the core logic for scraping the in5 startup directory.
It is designed to be controlled by main.py to scrape all startups for a
single, specified letter, making the process modular and robust.
"""

import time
import pandas as pd
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from urllib.parse import urljoin
import config

class InFiveScraper:
    """
    A scraper for the in5.ae startup directory, focused on scraping one
    alphabetical section at a time.
    """

    def __init__(self, page):
        """
        Initializes the scraper with an existing Playwright page object.
        
        Args:
            page: A Playwright page object to perform actions on.
        """
        self.page = page

    def scrape_by_letter(self, letter_to_scrape):
        """
        Scrapes all startups for a specific letter by clicking the filter,
        then repeatedly clicking 'Show more' and processing the results.

        Args:
            letter_to_scrape (str): The character to filter by (e.g., 'A', '#').

        Returns:
            pandas.DataFrame: A DataFrame containing all startups for the given letter.
        """
        all_startups_data = []
        processed_links = set()
        
        try:
            print(f"\n--- Starting scrape for letter: '{letter_to_scrape}' ---")
            
            # --- Step 1: Click the letter filter ---
            # Based on the screenshot, the selector can be specific.
            letter_selector = f"a.startup-alphabet-search[data-alphabet='{letter_to_scrape}']"
            print(f"  -> Clicking filter for '{letter_to_scrape}'...")
            self.page.locator(letter_selector).click()
            # Wait for the initial batch of startups to load after the click
            time.sleep(config.ACTION_DELAY * 2)

            # --- Step 2: Repeatedly click 'Show more' and scrape ---
            show_more_button_selector = "#LoadMoreTechStartups a.primaryBtn"
            
            while True:
                # Find all startup cards currently visible
                startup_elements = self.page.locator("div.listingItemLI").all()
                new_startups_found_in_batch = 0

                for element in startup_elements:
                    try:
                        profile_link = urljoin(config.BASE_URL, element.locator("a").first.get_attribute("href", timeout=5000))
                        if profile_link in processed_links:
                            continue

                        name = element.locator("h1.listingTitle").inner_text(timeout=5000).strip()
                        industry = element.locator("h1.listingTitle + div.listingDescription span").first.inner_text(timeout=5000).strip()
                        description = element.locator("div.listingDescription").nth(1).inner_text(timeout=5000).strip()

                        all_startups_data.append({
                            "name": name, "in5_profile_link": profile_link,
                            "industry": industry, "profile_description": description
                        })
                        processed_links.add(profile_link)
                        new_startups_found_in_batch += 1
                    except Exception as e:
                        # This can happen if a card is malformed, skip it.
                        continue
                
                if new_startups_found_in_batch > 0:
                    print(f"  -> Scraped {new_startups_found_in_batch} new startups. Total for '{letter_to_scrape}': {len(all_startups_data)}")

                # Check if the 'Show more' button is still visible and click it
                if self.page.is_visible(show_more_button_selector):
                    try:
                        print("  -> Clicking 'Show more'...")
                        self.page.locator(show_more_button_selector).click(timeout=10000)
                        time.sleep(config.ACTION_DELAY)
                    except PlaywrightTimeoutError:
                        print("  -> 'Show more' button timed out. Finishing letter.")
                        break
                else:
                    print(f"  -> No more 'Show more' button for letter '{letter_to_scrape}'.")
                    break
            
            print(f"--- Finished scraping for letter '{letter_to_scrape}'. Found {len(all_startups_data)} startups. ---")
            return pd.DataFrame(all_startups_data)

        except Exception as e:
            print(f"❌ An unexpected error occurred while scraping letter '{letter_to_scrape}': {e}")
            # Return what we have so far for this letter
            return pd.DataFrame(all_startups_data)
