# app_scraper.py

"""
This module contains the logic for scraping app stores to find out
if a company has a mobile application, focusing on specific data points.
It includes validation to ensure the found app belongs to the company.
"""

import requests
from google_play_scraper import search as search_play_store, app as app_play_store
from concurrent.futures import ThreadPoolExecutor, as_completed
import config
import re
import json

class AppScraper:
    """
    Searches for and scrapes detailed data from the Google Play Store and Apple App Store
    for a given company, with validation to match the app to the company.
    """

    def _clean_company_name(self, name):
        """Removes common suffixes like 'LLC', 'FZCO', etc., for better matching."""
        # This regex removes common business suffixes and punctuation.
        return re.sub(r'[,.\s]*(llc|fzco|inc|ltd|co|gmbh)[\s.]*$', '', name, flags=re.IGNORECASE).strip()

    def _format_google_play_details(self, details):
        """Formats Google Play app details into a structured dictionary."""
        return {
            "store": "Google Play",
            "title": details.get('title'),
            "description": details.get('description'),
            "genre": details.get('genre'),
            "installs": details.get('installs'),
            "score": details.get('score'),
            "ratings": details.get('ratings'),
            "free": details.get('free'),
            "developer": details.get('developer'),
            "developerEmail": details.get('developerEmail'),
            "url": details.get('url')
        }

    def _format_apple_store_details(self, details):
        """Formats Apple App Store details into a structured dictionary."""
        return {
            "store": "Apple App Store",
            "title": details.get('trackName'),
            "description": details.get('description'),
            "genre": details.get('primaryGenreName'),
            "installs": None,  # Not available via this API
            "score": details.get('averageUserRating'),
            "ratings": details.get('userRatingCount'),
            "free": details.get('price', -1) == 0.0,
            "developer": details.get('artistName'),
            "developerEmail": None, # Not available via this API
            "url": details.get('trackViewUrl')
        }

    def _search_apple_app_store(self, term, country, limit):
        """Searches the Apple App Store using the official iTunes Search API."""
        url = "https://itunes.apple.com/search"
        params = {"term": term, "country": country, "media": "software", "limit": limit}
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            return response.json().get('results', [])
        except requests.RequestException as e:
            print(f"    ⚠️ An error occurred during Apple App Store API call: {e}")
            return []

    def _scrape_google_play(self, company_name):
        """
        Scrapes the Google Play Store, searching for an app and validating
        it by matching the developer name with the company name.
        """
        try:
            # Search for multiple apps to find the best match.
            search_results = search_play_store(query=company_name, n_hits=config.NO_OF_APPS_TO_SCRAPE, country="ae")
            
            cleaned_company_name = self._clean_company_name(company_name).lower()

            for result in search_results:
                app_id = result['appId']
                # Fetch detailed info to get the developer name
                details = app_play_store(app_id, lang='en', country='ae')
                developer_name = details.get('developer', '').lower()
                
                # --- Validation Logic ---
                # Check if the cleaned company name is in the developer's name.
                if cleaned_company_name in developer_name:
                    print(f"    -> Found and validated Google Play app: {app_id}")
                    return self._format_google_play_details(details)

        except Exception as e:
            print(f"    ⚠️ An error occurred during Google Play scraping for '{company_name}': {e}")
        return None

    def _scrape_apple_store(self, company_name):
        """
        Scrapes the Apple App Store, searching for an app and validating
        it by matching the developer name (artistName) with the company name.
        """
        try:
            # Search for multiple apps to find the best match.
            search_results = self._search_apple_app_store(term=company_name, country="ae", limit=config.NO_OF_APPS_TO_SCRAPE)
            
            cleaned_company_name = self._clean_company_name(company_name).lower()

            for result in search_results:
                developer_name = result.get('artistName', '').lower()
                
                # --- Validation Logic ---
                # Check if the cleaned company name is in the developer's name.
                if cleaned_company_name in developer_name:
                    app_name = result.get('trackName')
                    print(f"    -> Found and validated Apple App Store app: {app_name}")
                    return self._format_apple_store_details(result)

        except Exception as e:
            print(f"    ⚠️ An error occurred during Apple Store scraping for '{company_name}': {e}")
        return None

    def scrape_apps(self, company_name):
        """
        Searches both app stores concurrently for a company's app and prints
        the combined results as a JSON object for debugging.
        
        Returns:
            list: A list of dictionaries, where each dictionary contains detailed app info.
        """
        app_details_list = []
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix='AppStoreScraper') as executor:
            future_google = executor.submit(self._scrape_google_play, company_name)
            future_apple = executor.submit(self._scrape_apple_store, company_name)

            for future in as_completed([future_google, future_apple]):
                try:
                    result = future.result()
                    if result:
                        app_details_list.append(result)
                except Exception as e:
                    print(f"    ⚠️ An error occurred in an app scraping thread: {e}")
        
        # --- Debugging Output ---
        # Print the final list of found apps as a JSON object.
        if app_details_list:
            print(f"  -> JSON Data for '{company_name}': {json.dumps(app_details_list, indent=2)}")
        else:
            print(f"  -> No validated mobile apps found for '{company_name}' in either store.")
            
        return app_details_list
