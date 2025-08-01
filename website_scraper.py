# website_scraper.py

"""
This module contains the logic for visiting a company's website to
determine if it has login or sign-up functionality. It is designed
to be used within a concurrent workflow.
"""

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import config
import re

class WebsiteScraper:
    """
    Scrapes a given website URL to check for the presence of login or
    sign-up links and buttons.
    """

    def __init__(self):
        """Initializes the scraper with the keywords to search for."""
        # Pre-compile a single regex for efficiency.
        # This creates a case-insensitive pattern like: (log in|login|sign in|...)
        self.keywords_regex = re.compile(
            "|".join(config.LOGIN_SIGNUP_KEYWORDS), 
            re.IGNORECASE
        )

    def check_for_login_or_signup(self, url: str) -> bool:
        """
        Visits a URL and checks for login/signup keywords in interactive elements.

        This method is thread-safe as it manages its own Playwright instance.

        Args:
            url (str): The website URL to check.

        Returns:
            bool: True if a login or signup element is found, False otherwise.
        """
        if not url or not url.startswith(('http://', 'https://')):
            print(f"    -> Invalid or missing URL: '{url}'. Skipping website scan.")
            return False

        print(f"    -> Scanning website: {url}")
        
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=config.HEADLESS_MODE)
                context = browser.new_context(
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                )
                page = context.new_page()
                
                try:
                    page.goto(url, timeout=config.WEBSITE_SCAN_TIMEOUT, wait_until='domcontentloaded')
                except PlaywrightTimeoutError:
                    print(f"    ⚠️ Timeout error when navigating to {url}. The site might be slow or down.")
                    browser.close()
                    return False
                except Exception as nav_error:
                    print(f"    ⚠️ Navigation error for {url}: {nav_error}")
                    browser.close()
                    return False

                # Combine selectors for buttons and links for a single, efficient query
                # This looks for any <a> or <button> element on the page.
                interactive_elements = page.locator("a, button")
                
                count = interactive_elements.count()
                for i in range(count):
                    element = interactive_elements.nth(i)
                    try:
                        element_text = element.text_content(timeout=1000)
                        if element_text and self.keywords_regex.search(element_text):
                            print(f"    ✅ Found keyword in element on {url}: '{element_text.strip()}'")
                            browser.close()
                            return True
                    except PlaywrightTimeoutError:
                        # This can happen if the element disappears from the DOM.
                        continue # Move to the next element
                
                browser.close()

        except Exception as e:
            print(f"    ❌ An unexpected error occurred while scanning {url}: {e}")
            return False
            
        print(f"    -> No login/signup keywords found on {url}")
        return False
