from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
import time
from dotenv import load_dotenv
import os
import glob
import sys  # Add this import to handle command-line arguments
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

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

# Locate the password input by ID
password_input = driver.find_element(By.ID, 'user_password')  # Locate the password input by ID
password_input.send_keys(os.getenv('MONDAY_PASSWORD'))  # Use password from .env

# Click the login button
login_button = driver.find_element(By.XPATH, '//button[@aria-label="Log in" and contains(@class, "submit_button")]')  # Updated XPath for the login button
login_button.click()

time.sleep(5)  # Wait for login to complete

# Navigate to Lark to find the email verification for monday
driver.get('https://qvantage.sg.larksuite.com/mail')

# Wait for the email page to load
time.sleep(5)  # Added wait to ensure the page is fully loaded

# Find and fill the login form
email_input = driver.find_element(By.CSS_SELECTOR, 'input[data-test="login-mail-input"]')  # Ensure this selector matches the HTML structure
email_input.send_keys(os.getenv('LARK_EMAIL'))  # Use email from .env

# Click the Terms and services button
checkbox = driver.find_element(By.CSS_SELECTOR, 'input.ud__checkbox__input')
checkbox.click()    

# Click the "Next" button after accepting terms
next_button = driver.find_element(By.CSS_SELECTOR, 'button[data-test="login-phone-next-btn"]')
next_button.click()  # Click the Next button

# Locate the password input using the correct selector
password_input = WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.CSS_SELECTOR, 'input[data-test="login-pwd-input"]'))  # Updated selector for password input
)
password_input.send_keys(os.getenv('LARK_PASSWORD'))  # Use password from .env

# Click the "Next" button after entering the password
next_button = driver.find_element(By.CSS_SELECTOR, 'button[data-test="login-pwd-next-btn"]')  # Locate the Next button
next_button.click()  # Click the Next button


time.sleep(5)  # Wait for login to complete

# Find the email from the specified sender
newest_email = WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.XPATH, '//span[contains(text(), "monday.com") and contains(@class, "sender-name")]'))  # Adjusted XPath for the sender
)

# Click on the newest email
newest_email.click()  # Click the email to open it

# Switch to the new tab or window if necessary
driver.switch_to.window(driver.window_handles[-1])  # Switch to the latest opened tab

# Click the "Login" button in the email
login_button_in_email = WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.XPATH, '//a[contains(text(), "Login")]'))  # Adjusted XPath for the Login button
)
login_button_in_email.click()  # Click the Login button


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