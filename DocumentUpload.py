from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Initialize the WebDriver
driver = webdriver.Safari()  # Changed from Chrome to Safari

# Open Monday.com and log in
driver.get('https://monday.com')
time.sleep(2)  # Wait for the page to load

# Find and fill the login form
email_input = driver.find_element(By.NAME, 'email')
email_input.send_keys(os.getenv('MONDAY_EMAIL'))  # Use email from .env
password_input = driver.find_element(By.NAME, 'password')
password_input.send_keys(os.getenv('MONDAY_PASSWORD'))  # Use password from .env
password_input.send_keys(Keys.RETURN)

time.sleep(5)  # Wait for login to complete

# Navigate to the specific board and column
driver.get('https://gobingo.monday.com/boards/1903060375')
time.sleep(2)

# Find the column and upload the image
upload_button = driver.find_element(By.XPATH, 'xpath_to_upload_button')
upload_button.send_keys('/path/to/your/image.jpg')

# Close the WebDriver
driver.quit()
