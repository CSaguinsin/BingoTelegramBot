from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time
from dotenv import load_dotenv
import os
import glob
import sys  # Add this import to handle command-line arguments

# Load environment variables from .env file
load_dotenv()

# Initialize the WebDriver
driver = webdriver.Safari()  # Changed from Chrome to Safari

# Open Monday.com and log in
driver.get('https://gobingo.monday.com/auth/login_monday/')  # Updated URL
time.sleep(2)  # Wait for the page to load

# Find and fill the login form
email_input = driver.find_element(By.ID, 'user_email')  # Locate the email input by ID
email_input.send_keys(os.getenv('MONDAY_EMAIL'))  # Use email from .env

# Click the 'Next' button
next_button = driver.find_element(By.XPATH, '//button[@aria-label="Next"]')  # Locate the Next button
next_button.click()  # Click the button to proceed

time.sleep(5)  # Wait for the next page to load

# Locate the password input by ID
password_input = driver.find_element(By.ID, 'user_password')  # Locate the password input by ID
password_input.send_keys(os.getenv('MONDAY_PASSWORD'))  # Use password from .env

# Click the login button
login_button = driver.find_element(By.XPATH, '//button[@aria-label="Log in"]')  # Locate the login button by aria-label
login_button.click()

time.sleep(5)  # Wait for login to complete

# Navigate to the specific board and column
driver.get('https://gobingo.monday.com/boards/1903060375')
time.sleep(2)

# Find the column for uploading documents
# Adjust the XPath to locate the correct column for 'Documents Uploaded'
upload_column = driver.find_element(By.XPATH, '//div[@data-column-id="file"]')  # Adjusted for the file column
upload_buttons = upload_column.find_elements(By.XPATH, './/input[@type="file"]')

# Upload images from the specified paths passed as arguments
if len(sys.argv) > 1:  # Check if image paths are provided
    image_paths = sys.argv[1:]  # Get image paths from command-line arguments
else:
    image_folder = '/Users/carlsaginsin/Projects/BingoTelegramBot/image_folder/*.jpg'
    image_paths = glob.glob(image_folder)  # Fallback to default folder

for image_path in image_paths:
    upload_buttons[0].send_keys(image_path)  # Upload each image

# Close the WebDriver
driver.quit()