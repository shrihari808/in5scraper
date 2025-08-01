# infive_scraper.py

"""
This module contains the core logic for scraping the in5 startup directory.
It is designed to be controlled by main.py to scrape all startups for a
single, specified letter, making the process modular and robust.
"""

import time
import pandas as pd
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, Error as PlaywrightError
from urllib.parse import urljoin
import config

class InFiveScraper:
    """
    A scraper for the in5.ae startup directory, focused on scraping one
    alphabetical section at a time.
    """

    def __init__(self, browser, page):
        """
        Initializes the scraper with an existing Playwright page object.
        
        Args:
            browser: The main Playwright browser instance.
            page: A Playwright page object to perform actions on.
        """
        self.browser = browser
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
            
            # --- Step 1: Wait for the initial page to load and get a baseline ---
            try:
                self.page.wait_for_selector("div.listingItemLI a", timeout=15000)
                first_startup_href_before_filter = self.page.locator("div.listingItemLI a").first.get_attribute("href")
            except PlaywrightTimeoutError:
                print("  -> Page did not load initial startup list. Skipping letter.")
                return pd.DataFrame()

            # --- Step 2: Click the letter filter and wait for the content to be replaced ---
            letter_selector = f"a.startup-alphabet-search[data-alphabet='{letter_to_scrape}']"
            print(f"  -> Clicking filter for '{letter_to_scrape}'...")
            self.page.locator(letter_selector).click()

            try:
                self.page.wait_for_function(
                    f"document.querySelector('div.listingItemLI a')?.getAttribute('href') !== '{first_startup_href_before_filter}'",
                    timeout=10000
                )
                print("  -> Filtered startup list loaded.")
            except PlaywrightTimeoutError:
                print(f"  -> No unique startups found for letter '{letter_to_scrape}'. The list did not change after filtering.")
                return pd.DataFrame()

            # --- Step 3: Repeatedly click 'Show more' and scrape ---
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
                        
                        industry = ""
                        description = ""
                        website_url = ""
                        
                        description_divs = element.locator("div.listingDescription")
                        for i in range(description_divs.count()):
                            div = description_divs.nth(i)
                            try:
                                strong_tag = div.locator("strong")
                                if strong_tag.count() > 0:
                                    strong_text = strong_tag.inner_text(timeout=500).strip()
                                    full_text = div.inner_text(timeout=500).strip()
                                    content = full_text.replace(strong_text, '', 1).strip()
                                    
                                    if "Industry" in strong_text:
                                        industry = content
                                    elif "Profile" in strong_text:
                                        description = content
                                    elif "Website" in strong_text:
                                        website_url = content
                            except PlaywrightTimeoutError:
                                continue

                        # --- Website Validation Step ---
                        is_valid_startup = True
                        if website_url:
                            if not website_url.startswith(('http://', 'https://')):
                                website_url = 'http://' + website_url
                            
                            print(f"    -> Validating website: {website_url} ...")
                            validation_context = None
                            try:
                                # **FIX**: Create a new, isolated browser context for each validation.
                                validation_context = self.browser.new_context()
                                validation_page = validation_context.new_page()
                                
                                response = validation_page.goto(website_url, timeout=15000, wait_until='domcontentloaded')
                                
                                if not response or not response.ok:
                                    print(f"    -> ❌ Invalid response for {website_url}. Status: {response.status if response else 'N/A'}")
                                    is_valid_startup = False
                                else:
                                    print(f"    -> ✅ Website is valid.")
                            except PlaywrightError:
                                print(f"    -> ❌ Website failed to load: {website_url}")
                                is_valid_startup = False
                            finally:
                                # **FIX**: Close the entire context, not just the page.
                                if validation_context:
                                    validation_context.close()
                        
                        if is_valid_startup:
                            all_startups_data.append({
                                "name": name, "in5_profile_link": profile_link,
                                "website": website_url, "industry": industry,
                                "profile_description": description
                            })
                        else:
                            print(f"    -> Skipping startup '{name}' due to invalid website.")
                        
                        processed_links.add(profile_link)

                    except Exception as e:
                        print(f"    -> Warning: Could not process a startup card. Error: {e}")
                        continue
                
                # --- Step 4: Check for and click the 'Show more' button ---
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
            
            print(f"--- Finished scraping for letter '{letter_to_scrape}'. Found {len(all_startups_data)} valid startups. ---")
            return pd.DataFrame(all_startups_data)

        except Exception as e:
            print(f"❌ An unexpected error occurred while scraping letter '{letter_to_scrape}': {e}")
            return pd.DataFrame(all_startups_data)
