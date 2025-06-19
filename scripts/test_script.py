from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

def test_chrome_driver():
    try:
        options = Options()
        # Don't add headless mode — let the browser open visibly

        service = Service('./chromedriver.exe')  # Adjust path if needed

        driver = webdriver.Chrome(service=service, options=options)
        driver.get("https://www.google.com")
        print("✅ ChromeDriver launched and opened Google visibly.")
        input("🔍 Press Enter to close browser...")  # Pause to view
        driver.quit()
    except Exception as e:
        print(f"❌ ChromeDriver failed: {e}")

test_chrome_driver()
