from playwright.sync_api import sync_playwright

URL = "https://www.scribd.com/document/4026761/Intelligent-Platform-Management-Interface-Specification-v1-0#google_vignette"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(URL, wait_until="domcontentloaded", timeout=60_000)
        print("Title:", page.title())
        page.screenshot(path="screenshot.png")
        input("Browser is open. Press Enter to close...")
        browser.close()


if __name__ == "__main__":
    main()
