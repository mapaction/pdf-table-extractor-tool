from streamlit import cache_data
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
# from bs4 import BeautifulSoup
# import time
# import re
# from datetime import datetime

@cache_data(ttl=3600, show_spinner=False)  # cache result for 1h (3600s)
def get_latest_id(url="https://ehtools.org/document-register"): # maximum pdf ID
    """Scrapes the latest ID fr


st.markdoom the given URL using Selenium in headless mode.
    Returns the extracted string or None if not found.

    url - input URL to be scraped
    """
    # Configure Chrome options for headless mode
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")   # Headless mode (use "--headless=new" for Chrome 109+)
    chrome_options.add_argument("--disable-gpu")    # Good practice on Windows
    chrome_options.add_argument("--no-sandbox")     # Often needed in Linux environments
    chrome_options.add_argument("--disable-dev-shm-usage")  # Helps with limited resource issues

    # Point to Chromium binary (on Streamlit Cloud)
    chromium_path = "/usr/bin/chromium"
    if os.path.exists(chromium_path):
        chrome_options.binary_location = chromium_path

    # Point to chromedriver
    service = Service("/usr/bin/chromedriver")
    # # Ensure chromedriver runs silently (Windows-specific)
    # service = Service()
    try:
        service.creationflags = 0x08000000  # CREATE_NO_WINDOW (Windows only)
    except AttributeError:
        pass  # On Linux/macOS, this flag isn't available
  
    driver = webdriver.Chrome(service=service, options=chrome_options) 
    driver.get(url)

    wait = WebDriverWait(driver, 5)

    try:
        strong_element = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "td.sorting_1.dtr-control strong.text-primary"))
        )
        value = strong_element.text.strip()
        # print(value)
    except:
        value = None
    # value = driver.find_element(By.CSS_SELECTOR, "td.sorting_1.dtr-control strong.text-primary").text
    # print("Latest id:", value)

    driver.quit()

    return int(value)

# print(get_latest_id())
