# modules/cfa_scrape_data.py

import boto3
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options  # Ensure Options is imported
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
import requests
import snowflake.connector
from dotenv import load_dotenv

def init_s3():
    load_dotenv()
    # AWS S3 Initialization
    bucket_name = os.getenv('AWS_BUCKET')
    aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')

    s3 = boto3.client(
        's3',
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key
    )
    return s3, bucket_name

def init_snowflake():
    load_dotenv()
    # Snowflake Initialization
    user = os.getenv('SNOWFLAKE_USER')
    password = os.getenv('SNOWFLAKE_PASSWORD')
    account = os.getenv('SNOWFLAKE_ACCOUNT')
    warehouse = os.getenv('SNOWFLAKE_WAREHOUSE')
    database = os.getenv('SNOWFLAKE_DATABASE')
    schema = os.getenv('SNOWFLAKE_SCHEMA')

    snowflake_conn = snowflake.connector.connect(
        user=user,
        password=password,
        account=account,
        warehouse=warehouse,
        database=database,
        schema=schema,
    )
    return snowflake_conn

def init_driver():
    # Set the path to the ChromeDriver
    chrome_driver_path = '/usr/local/bin/chromedriver'
    service = Service(executable_path=chrome_driver_path)

    # Initialize WebDriver with download options
    options = Options()
    options.add_experimental_option('prefs', {
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True  # Ensure PDFs are downloaded instead of opened in browser
    })
    # Add headless mode to avoid issues on servers without a GUI
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def upload_to_s3(s3, bucket_name, file_path, s3_key):
    s3.upload_file(file_path, bucket_name, s3_key)
    return f"https://{bucket_name}.s3.amazonaws.com/{s3_key}"

def save_metadata_to_snowflake(snowflake_conn, title, summary, image_s3_url, pdf_s3_url):
    cursor = snowflake_conn.cursor()
    query = """
    INSERT INTO publications_metadata (title, summary, image_url, pdf_url)
    VALUES (%s, %s, %s, %s)
    """
    cursor.execute(query, (title, summary, image_s3_url, pdf_s3_url))
    cursor.close()

def download_file(driver, file_url, save_path):
    # Get current cookies
    cookies = driver.get_cookies()
    s = requests.Session()
    for cookie in cookies:
        s.cookies.set(cookie['name'], cookie['value'])

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
        'Referer': driver.current_url,
        'Accept': '*/*',
    }
    response = s.get(file_url, headers=headers, allow_redirects=True)
    if response.status_code == 200:
        content_type = response.headers.get('Content-Type', '')
        if 'application/pdf' in content_type or 'image' in content_type:
            with open(save_path, 'wb') as file:
                file.write(response.content)
        else:
            print(f"Download failed, incorrect content type: {content_type}")
    else:
        print(f"Download failed, status code: {response.status_code}")

def extract_publication(driver, publication, s3, bucket_name, snowflake_conn):
    try:
        publication_url = publication['url']
        title = publication['title']

        # Open a new tab
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[-1])

        # Visit the publication page
        driver.get(publication_url)
        time.sleep(5)  # Wait for the page to load

        # Try to get the summary
        try:
            summary_element = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'span.overview__content'))
            )
            summary = summary_element.text
        except Exception:
            summary = ''

        # Try to get the image URL
        try:
            image_element = driver.find_element(By.CSS_SELECTOR, 'img.article-cover')
            image_url = image_element.get_attribute('src')
            image_filename = os.path.basename(image_url).split('?')[0]
            # Download the image
            download_file(driver, image_url, image_filename)
            # Upload the image to S3
            image_s3_url = upload_to_s3(s3, bucket_name, image_filename, f'images/{image_filename}')
            # Remove the local image file
            os.remove(image_filename)
        except Exception:
            image_s3_url = None  # Or set to empty string ''

        # Get the PDF link
        try:
            pdf_link_element = driver.find_element(By.CSS_SELECTOR, 'a[href*=".pdf"]')
            pdf_url = pdf_link_element.get_attribute('href')
            pdf_filename = os.path.basename(pdf_url).split('?')[0]
            # Download the PDF
            download_file(driver, pdf_url, pdf_filename)
            # Upload the PDF to S3
            pdf_s3_url = upload_to_s3(s3, bucket_name, pdf_filename, f'pdfs/{pdf_filename}')
            # Remove the local PDF file
            os.remove(pdf_filename)
        except Exception:
            print("PDF link not found, skipping this publication.")
            # Close the current tab and switch back
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
            return False

        # Save metadata to Snowflake
        save_metadata_to_snowflake(snowflake_conn, title, summary, image_s3_url, pdf_s3_url)

        print(f"Title: {title}")
        print(f"Summary: {summary}")
        print(f"Image S3 URL: {image_s3_url}")
        print(f"PDF S3 URL: {pdf_s3_url}")
        print('------------------------')

        # Close the current tab and switch back
        driver.close()
        driver.switch_to.window(driver.window_handles[0])

        return True
    except Exception as e:
        print(f"Error processing publication: {e}")
        # Ensure the tab is closed and switch back
        if len(driver.window_handles) > 1:
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
        return False

def extract_publications(driver, s3, bucket_name, snowflake_conn):
    try:
        # Wait for all publication elements to load
        pub_elements = WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'h4.coveo-title a.CoveoResultLink'))
        )
        # Collect all publication URLs and titles
        publications = []
        for pub_element in pub_elements:
            publication_url = pub_element.get_attribute('href')
            title = pub_element.text
            publications.append({'url': publication_url, 'title': title})

        # Process each publication one by one
        for i, publication in enumerate(publications):
            print(f"Processing publication {i+1} on current page...")
            if not extract_publication(driver, publication, s3, bucket_name, snowflake_conn):
                print(f"Failed to process publication {i+1}, retrying...")
                if not extract_publication(driver, publication, s3, bucket_name, snowflake_conn):  # Retry
                    print(f"Still failed to process publication {i+1} after retry.")
        return True
    except Exception as e:
        print(f"Error extracting publications: {e}")
        return False

def close_popups(driver):
    try:
        # Check for overlay elements and try to close them
        overlay = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'div.overlay, div.modal, div.popup'))
        )
        close_button = overlay.find_element(By.CSS_SELECTOR, 'button.close, button.dismiss')
        close_button.click()
        print("Closed a popup or overlay element.")
        time.sleep(1)  # Wait for the overlay to disappear
    except Exception:
        pass  # Ignore if no overlay is found

def navigate_and_extract_all_publications(driver, s3, bucket_name, snowflake_conn, total_pages):
    for page in range(1, total_pages + 1):
        print(f"Extracting page {page}...")
        if not extract_publications(driver, s3, bucket_name, snowflake_conn):
            break

        if page < total_pages:
            try:
                # Ensure no overlay elements are present
                close_popups(driver)

                # Click the "Next" button
                next_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, '[aria-label="Next"]'))
                )
                driver.execute_script("arguments[0].scrollIntoView();", next_button)
                next_button.click()
                time.sleep(5)  # Wait for the new page to load
            except Exception as e:
                print(f"Error navigating to page {page+1}: {e}")
                break

def scrape_data():
    # Initialize resources
    s3, bucket_name = init_s3()
    snowflake_conn = init_snowflake()
    driver = init_driver()

    # Target URL
    url = 'https://rpc.cfainstitute.org/en/research-foundation/publications'

    # Open the webpage
    driver.get(url)
    time.sleep(5)  # Wait for the page to load

    # Ensure the correct filters are selected
    try:
        # Close any potential popups
        close_popups(driver)

        # Click the filter to select "Research Foundation"
        filter_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'div.facet-section-title[title="Series Content"]'))
        )
        filter_button.click()
        time.sleep(1)

        # Select "Research Foundation"
        research_foundation_option = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, 'li.facet-value[data-value="Research Foundation"]'))
        )
        research_foundation_option.click()
        time.sleep(2)  # Wait for the filter results to load
    except Exception as e:
        print(f"Error setting filters: {e}")

    # Start extracting all publications
    total_pages = 10
    navigate_and_extract_all_publications(driver, s3, bucket_name, snowflake_conn, total_pages)

    # Close the browser and connections
    driver.quit()
    snowflake_conn.close()

if __name__ == "__main__":
    scrape_data()
