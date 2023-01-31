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
LOTING = WONINGNET + "Zoeken#model[Loting]~predef[2]"
REGULIER = (
    WONINGNET
    + "Zoeken#model[Regulier aanbod]~soort[Exclusief situatiepunten,Inclusief situatiepunten]~predef[]"
)
MAX_REACTIES = 2

## TODO Make it run on the t4v1 server
## TODO Improve logging by making messages more specific


def jsClick(el):
    b.execute_script("arguments[0].click();", el)


def noCookies():
    try:
        accept_cookies = b.find_element(By.CSS_SELECTOR, ".cc-cookie-accept")
        jsClick(accept_cookies)
        time.sleep(2)
        close_notification = b.find_element(By.CSS_SELECTOR, ".growl-notification .close")
        jsClick(close_notification)
    except Exception as e:
        logging.error(e)
        mailLog()
        b.quit()


def login():
    try:
        b.get(LOGIN)
        b.find_element(By.ID, "gebruikersnaam").send_keys(config.username)
        b.find_element(By.ID, "password").send_keys(config.password)
        login = b.find_element(By.ID, "loginButton")
        jsClick(login)
    except Exception as e:
        logging.error(e)
        mailLog()
        b.quit()


def reagerenGelukt(b):
    try:
        reageren_button = b.find_element(By.CSS_SELECTOR, ".interactionColumn .primary.button")
        reageren_button_innerText = reageren_button.get_attribute("innerText")
        reageren_button_text = re.sub("[^a-z^A-Z]+", "", reageren_button_innerText)

        if reageren_button_text == "Reageren":
            jsClick(reageren_button)
            time.sleep(5)

            tab = b.find_element(By.CSS_SELECTOR, ".tabMenuContainer dd:not(.active)")
            jsClick(tab)

            checkbox = b.find_element(By.CSS_SELECTOR, "#akkoordContainer label")
            jsClick(checkbox)

            submit = b.find_element(By.ID, "formsubmitbutton")
            jsClick(submit)

            time.sleep(5)

            return True
        elif reageren_button_text == "Al gereageerd":
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
        unit_links = b.find_elements(By.CSS_SELECTOR, ".unitContainer > a.unitLink:first-of-type")

        i = 0
        for unit in unit_links:
            if i < aantal_reacties:
                link = unit.get_attribute("href")
                b.execute_script("window.open('" + link + "', '_blank');")
                b.switch_to.window(b.window_handles[1])
                time.sleep(3)

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


def lotingBeschikbaar():
    try:
        b.get(LOTING)
        time.sleep(5)
        b.refresh()
        time.sleep(5)
        active_tab = b.find_element(By.CSS_SELECTOR, ".tabMenu > li:last-of-type a")
        active_tab_text = active_tab.get_attribute("innerText")
        logging.info("Loting tab text: " + active_tab_text)

        active_tab_title = re.sub("[^a-z^A-Z]+", "", active_tab_text)

        if active_tab_title == "Loting":
            logging.info("Loting woningen are available")
            return True
        else:
            logging.info("No Loting woningen available")
        return False
    except Exception as e:
        logging.info("An error ocurred while checking if lotingBeschikbaar")
        logging.error(e)
        mailLog()
        b.quit()


def aantalReacties(url):
    try:
        b.get(url)
        time.sleep(10)
        unit_links = b.find_elements(By.CSS_SELECTOR, ".unitContainer > a.unitLink:first-of-type")

        visible_notifications = 0
        unit_notifications = b.find_elements(By.CSS_SELECTOR, ".unitNotification")
        for n in unit_notifications:
            if b.execute_script("return arguments[0].style.display;", n) != "none":
                visible_notifications += 1

        if len(unit_links) == visible_notifications:
            logging.info("No woningen on " + url + " left to react on.")
            return 0
        return visible_notifications
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
service = FirefoxService("/usr/bin/geckodriver", log_path="/dev/null")
opts.add_argument('-headless')
b = webdriver.Firefox(options=opts, service=service)

b.get(WONINGNET)
noCookies()
login()

aantal_reguliere_reacties = MAX_REACTIES - aantalReacties(REGULIER)
if aantal_reguliere_reacties > 0:
    logging.info("Aantal reguliere reacties available: " + str(aantal_reguliere_reacties))
    reageerOp(REGULIER, aantal_reguliere_reacties)
else:
    logging.info("No reguliere woning reacties left")

# if lotingBeschikbaar():
#     aantal_loting_reacties = aantalReacties(LOTING)
#     logging.info("Aantal loting reacties available: " + str(aantal_loting_reacties))
#     # if aantal_loting_reacties < MAX_REACTIES:
#     #     reageerOp(LOTING, aantal_loting_reacties)
#     # else:
#     #     logging.info("No loting woning reacties left")
#     reageerOp(LOTING, MAX_REACTIES)

b.quit()
mailLog()