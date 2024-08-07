import config
import re
import os
import time
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from selenium import webdriver
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

WONINGNET = "https://www.woningnetregioamsterdam.nl/"
LOGIN = WONINGNET + "Inloggen"
OVERZICHT = (WONINGNET + "WoningOverzicht")
REACTIES = (WONINGNET + "ReactieOverzicht")
MAX_REACTIES = 2


def jsClick(el):
    b.execute_script("arguments[0].click();", el)


def noCookies():
    try:
        time.sleep(2)
        accept_cookies = b.find_element(By.ID, "cookiescript_accept")
        jsClick(accept_cookies)
        time.sleep(2)
    except Exception as e:
        logging.error(e)
        mailLog()
        b.quit()


def login():
    try:
        b.find_element(By.ID, "Input_UsernameVal").send_keys(config.username)
        b.find_element(By.ID, "Input_PasswordVal").send_keys(config.password)
        login = b.find_element(By.CSS_SELECTOR, "#b8-Button button")
        jsClick(login)
        time.sleep(5)
    except Exception as e:
        logging.error(e)
        mailLog()
        b.quit()


def reagerenGelukt(b):
    try:
        reageren_button = b.find_element(By.CSS_SELECTOR, ".inhetkort .btn.OSFillParent")
        reageren_button_innerText = reageren_button.get_attribute("innerText")

        if reageren_button_innerText == "Reageren op deze woning":
            jsClick(reageren_button)
            time.sleep(5)
            return True
        elif reageren_button_innerText == "Reactie intrekken":
            logging.info("Already reacted to woning: " + b.current_url)
            return False
        else:
            return False

    except Exception as e:
        logging.error(e)
        mailLog()
        b.quit()


def reageerOp(url, aantal_reacties):
    try:
        b.get(url)
        time.sleep(10)
        unit_links = b.find_elements(By.CSS_SELECTOR, ".OSBlockWidget > a")

        i = 0
        for unit in unit_links:
            if i < aantal_reacties:
                link = unit.get_attribute("href")
                b.execute_script("window.open('" + link + "', '_blank');")
                b.switch_to.window(b.window_handles[1])
                time.sleep(10)

                if reagerenGelukt(b):
                    i += 1
                    b.close()
                    logging.info("Reacted to woning: " + link)
                else:
                    logging.info("Skipping: " + link)
                    b.close()

                b.switch_to.window(b.window_handles[0])
                time.sleep(3)
    except Exception as e:
        logging.error(e)
        mailLog()
        b.quit()


def aantalReacties(url):
    try:
        b.get(url)
        time.sleep(15)
        return int(b.find_element(By.CSS_SELECTOR, "#HaalActueleReacties_Count span").text)
    except Exception as e:
        logging.info("An error ocurred while checking the aantalReacties")
        logging.error(e)
        mailLog()
        b.quit()


def mailLog():
    msg = MIMEMultipart()
    msg["Subject"] = "Log"
    msg["From"] = "Auto WoningNet <" + config.send_email + ">"
    msg["To"] = config.receive_email
    msg.attach(MIMEText(open(config.log_path).read()))

    try:
        smtpObj = smtplib.SMTP_SSL(config.outgoing_smtp)
        smtpObj.connect(config.outgoing_smtp, 465)
        smtpObj.ehlo()
        smtpObj.login(config.send_email, config.email_pass)
        smtpObj.sendmail(config.send_email, config.receive_email, msg.as_string())
        smtpObj.quit()
    except Exception as e:
        print(e)
    else:
        if os.path.exists(config.log_path):
            os.remove(config.log_path)


logging.basicConfig(filename=config.log_path, level=logging.INFO)

opts = Options()
service = FirefoxService("/usr/local/bin/geckodriver", log_path="/dev/null")
opts.add_argument('-headless')
b = webdriver.Firefox(options=opts, service=service)

b.get(WONINGNET)
noCookies()
login()

aantal_reguliere_reacties = MAX_REACTIES - aantalReacties(REACTIES)
if aantal_reguliere_reacties > 0:
    logging.info("Aantal reguliere reacties available: " + str(aantal_reguliere_reacties))
    time.sleep(5)
    reageerOp(OVERZICHT, aantal_reguliere_reacties)
else:
    logging.info("No reguliere woning reacties left")

b.quit()
mailLog()