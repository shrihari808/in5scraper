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
            
            # --- Step 1: Click the letter filter and wait for results ---
            letter_selector = f"a.startup-alphabet-search[data-alphabet='{letter_to_scrape}']"
            print(f"  -> Clicking filter for '{letter_to_scrape}'...")
            self.page.locator(letter_selector).click()

            try:
                self.page.wait_for_selector("div.listingItemLI", timeout=15000)
                print("  -> Initial startup list loaded.")
            except PlaywrightTimeoutError:
                print(f"  -> No startups found for letter '{letter_to_scrape}' after clicking filter. Skipping.")
                return pd.DataFrame()

            # --- Step 2: Repeatedly click 'Show more' and scrape ---
            show_more_button_selector = "#loadMoreTechStartups a.primaryBtn"
            
            while True:
                initial_startup_count = len(self.page.locator("div.listingItemLI").all())
                startup_elements = self.page.locator("div.listingItemLI").all()
                
                for element in startup_elements:
                    try:
                        link_element = element.locator("a").first
                        href = link_element.get_attribute("href", timeout=5000)
                        if not href:
                            continue

                        profile_link = urljoin(config.BASE_URL, href)
                        if profile_link in processed_links:
                            continue

                        name = element.locator("h1.listingTitle").inner_text(timeout=5000).strip()
                        
                        # **FIX**: New logic to find industry and description based on labels.
                        # It iterates through description divs and checks the <strong> tag.
                        industry = ""
                        description = ""
                        
                        description_divs = element.locator("div.listingDescription")
                        for i in range(description_divs.count()):
                            div = description_divs.nth(i)
                            try:
                                strong_tag = div.locator("strong")
                                # Check if a <strong> tag exists within this div
                                if strong_tag.count() > 0:
                                    strong_text = strong_tag.inner_text(timeout=500).strip()
                                    full_text = div.inner_text(timeout=500).strip()
                                    
                                    # Assign data based on the label in the <strong> tag
                                    if "Industry" in strong_text:
                                        industry = full_text.replace(strong_text, "", 1).strip()
                                    elif "Profile" in strong_text:
                                        description = full_text.replace(strong_text, "", 1).strip()
                            except PlaywrightTimeoutError:
                                # If a div times out, just skip it and check the next one.
                                continue

                        all_startups_data.append({
                            "name": name, "in5_profile_link": profile_link,
                            "industry": industry, "profile_description": description
                        })
                        processed_links.add(profile_link)
                    except Exception as e:
                        print(f"    -> Warning: Could not process a startup card. Error: {e}")
                        continue
                
                # --- Step 3: Check for and click the 'Show more' button ---
                show_more_button = self.page.locator(show_more_button_selector)
                if show_more_button.is_visible():
                    try:
                        print("  -> Clicking 'Show more'...")
                        show_more_button.click(timeout=10000)
                        
                        self.page.wait_for_function(
                            f"document.querySelectorAll('div.listingItemLI').length > {initial_startup_count}",
                            timeout=15000
                        )
                        print(f"  -> More startups loaded. Total now: {len(self.page.locator('div.listingItemLI').all())}")
                    except PlaywrightTimeoutError:
                        print("  -> 'Show more' was visible but did not load new content. Finishing letter.")
                        break
                else:
                    print(f"  -> No more 'Show more' button for letter '{letter_to_scrape}'.")
                    break
            
            print(f"--- Finished scraping for letter '{letter_to_scrape}'. Found {len(processed_links)} startups. ---")
            return pd.DataFrame(all_startups_data)

        except Exception as e:
            print(f"❌ An unexpected error occurred while scraping letter '{letter_to_scrape}': {e}")
            return pd.DataFrame(all_startups_data)
