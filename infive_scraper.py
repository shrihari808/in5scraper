# infive_scraper.py

"""
This module contains the core logic for scraping the in5 startup directory.
It is designed to be controlled by main.py to scrape all startups for a
single, specified letter, making the process modular and robust.
"""

import pandas as pd
from playwright.async_api import TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError
from urllib.parse import urljoin
import config

class InFiveScraper:
    """
    A scraper for the in5.ae startup directory, focused on scraping one
    alphabetical section at a time using an async-first approach.
    """

    def __init__(self, browser, page):
        """
        Initializes the scraper with an existing Playwright page object.
        
        Args:
            browser: The main async Playwright browser instance, needed for validation contexts.
            page: An async Playwright page object to perform actions on.
        """
        self.browser = browser
        self.page = page

    async def scrape_by_letter(self, letter_to_scrape):
        """
        Scrapes all startups for a specific letter by clicking the filter,
        then repeatedly clicking 'Show more' and processing the results.

        Args:
            letter_to_scrape (str): The character to filter by (e.g., 'A').

        Returns:
            pandas.DataFrame: A DataFrame containing all startups for the given letter.
        """
        all_startups_data = []
        processed_links = set()
        
        try:
            print(f"\n--- Starting scrape for letter: '{letter_to_scrape}' ---")
            
            # --- Step 1: Click the letter filter ---
            letter_selector = f"a.startup-alphabet-search[data-alphabet='{letter_to_scrape}']"
            print(f"  -> Clicking filter for '{letter_to_scrape}'...")
            await self.page.locator(letter_selector).click()
            await self.page.wait_for_timeout(3000) # Static wait for filter to apply

            # --- Step 2: Repeatedly click 'Show more' and scrape ---
            show_more_button_selector = "#loadMoreTechStartups a.primaryBtn"
            
            while True:
                startup_elements = await self.page.locator("div.listingItemLI").all()
                initial_startup_count = len(startup_elements)
                
                for element in startup_elements:
                    try:
                        link_element = element.locator("a").first
                        href = await link_element.get_attribute("href", timeout=5000)
                        if not href:
                            continue

                        profile_link = urljoin(config.BASE_URL, href)
                        if profile_link in processed_links:
                            continue
                        
                        processed_links.add(profile_link)

                        name = await element.locator("h1.listingTitle").inner_text(timeout=5000)
                        name = name.strip()
                        
                        industry = ""
                        description = ""
                        website_url = ""
                        
                        description_divs = element.locator("div.listingDescription")
                        for i in range(await description_divs.count()):
                            div = description_divs.nth(i)
                            try:
                                strong_tag = div.locator("strong")
                                if await strong_tag.count() > 0:
                                    strong_text = (await strong_tag.inner_text(timeout=500)).strip()
                                    full_text = (await div.inner_text(timeout=500)).strip()
                                    content = full_text.replace(strong_text, '', 1).strip()
                                    
                                    if "Industry" in strong_text:
                                        industry = content
                                    elif "Profile" in strong_text:
                                        description = content
                                    elif "Website" in strong_text:
                                        website_url = content
                            except PlaywrightTimeoutError:
                                continue
                        
                        all_startups_data.append({
                            "name": name, "in5_profile_link": profile_link,
                            "website": website_url, "industry": industry,
                            "profile_description": description
                        })

                    except Exception as e:
                        print(f"    -> Warning: Could not process a startup card. Error: {e}")
                        continue
                
                # --- Step 3: Check for and click the 'Show more' button ---
                show_more_button = self.page.locator(show_more_button_selector)
                if await show_more_button.is_visible():
                    try:
                        print("  -> Clicking 'Show more'...")
                        await show_more_button.click(timeout=10000)
                        
                        # Wait for new content to load
                        await self.page.wait_for_function(
                            f"document.querySelectorAll('div.listingItemLI').length > {initial_startup_count}",
                            timeout=15000
                        )
                        new_count = len(await self.page.locator('div.listingItemLI').all())
                        print(f"  -> More startups loaded. Total now: {new_count}")
                    except PlaywrightTimeoutError:
                        print("  -> 'Show more' was visible but did not load new content. Finishing letter.")
                        break
                else:
                    print(f"  -> No more 'Show more' button for letter '{letter_to_scrape}'.")
                    break
            
            print(f"--- Finished scraping for letter '{letter_to_scrape}'. Found {len(all_startups_data)} startups. ---")
            # Remove duplicates before returning
            if all_startups_data:
                df = pd.DataFrame(all_startups_data)
                df.drop_duplicates(subset=['in5_profile_link'], inplace=True)
                return df
            return pd.DataFrame()

        except Exception as e:
            print(f"❌ An unexpected error occurred while scraping letter '{letter_to_scrape}': {e}")
            return pd.DataFrame()
