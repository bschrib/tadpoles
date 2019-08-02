import os
import re
import sys
import pdb
import time
import shutil
import pickle
import logging
import logging.config
import imghdr
import datetime

from random import randrange
from getpass import getpass
from os.path import abspath, dirname, join, isfile, isdir

import requests
import lxml.html
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from xvfbwrapper import Xvfb


# -----------------------------------------------------------------------------
# Logging stuff
# -----------------------------------------------------------------------------
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': "%(asctime)s %(levelname)s %(module)s::%(funcName)s: %(message)s",
            'datefmt': '%H:%M:%S'
        }
    },
    'handlers': {
        'app': {'level': 'DEBUG',
                    'class': 'ansistrm.ColorizingStreamHandler',
                    'formatter': 'standard'},
        'default': {'level': 'ERROR',
                    'class': 'ansistrm.ColorizingStreamHandler',
                    'formatter': 'standard'},
    },
    'loggers': {
        'default': {
            'handlers': ['default'], 'level': 'ERROR', 'propagate': False
        },
         'app': {
            'handlers': ['app'], 'level': 'DEBUG', 'propagate': True
        },

    },
}
logging.config.dictConfig(LOGGING_CONFIG)


# -----------------------------------------------------------------------------
# The scraper code.
# -----------------------------------------------------------------------------
class DownloadError(Exception):
    pass


class Client:

    COOKIE_FILE = "state/cookies.pkl"
    ROOT_URL = "http://www.tadpoles.com/"
    HOME_URL = "https://www.tadpoles.com/parents"
    MIN_SLEEP = 1
    MAX_SLEEP = 6

    def __init__(self):
        self.init_logging()

    def init_logging(self):
        logger = logging.getLogger('app')
        self.info = logger.info
        self.debug = logger.debug
        self.warning = logger.warning
        self.critical = logger.critical
        self.exception = logger.exception

    def __enter__(self):
        self.info("Starting xvfb display")
        self.vdisplay = Xvfb()
        self.vdisplay.start()
        self.info("Starting browser")
        self.br = self.browser = webdriver.Firefox()
        self.br.implicitly_wait(10)
        return self

    def __exit__(self, *args):
        self.info("Shutting down browser")
        self.browser.quit()
        self.info("Shutting down xfvb display")
        self.vdisplay.stop()

    def sleep(self, minsleep=None, maxsleep=None):
        self.info("Executing sleep")
        _min = minsleep or self.MIN_SLEEP
        _max = maxsleep or self.MAX_SLEEP
        duration = randrange(_min * 100, _max * 100) / 100.0
        self.debug('Sleeping %r' % duration)
        time.sleep(duration)

    def navigate_url(self, url):
        self.info("Executing navigate_url")
        self.info("Navigating to %r", url)
        self.br.get(url)

    def load_cookies(self):
        self.info("Executing load_cookies")
        if not isdir('state'):
            os.mkdir('state')
        with open(self.COOKIE_FILE, "rb") as f:
            self.cookies = pickle.load(f)

    def dump_cookies(self):
        self.info("Executing dump_cookies")
        with open(self.COOKIE_FILE,"wb") as f:
            pickle.dump(self.br.get_cookies(), f)

    def add_cookies_to_browser(self):
        self.info("Executing add_cookies_to_browser")
        for cookie in self.cookies:
            if self.br.current_url.strip('/').endswith(cookie['domain']):
                self.br.add_cookie(cookie)

    def requestify_cookies(self):
        self.info("Executing requestify_cookies")
        # Cookies in the form reqeusts expects.
        self.info("Transforming the cookies for requests lib.")
        self.req_cookies = {}
        for s_cookie in self.cookies:
            self.req_cookies[s_cookie["name"]] = s_cookie["value"]

    def switch_windows(self):
        '''Switch to the other window.'''
        self.info("Executing switch_windows")
        all_windows = set(self.br.window_handles)
        self.info("Displaying all_windows")
        self.info(all_windows)
        current_window = set([self.br.current_window_handle])
        self.info("Displaying current_window")
        self.info(current_window)
        other_window = (all_windows - current_window).pop()
        self.info("Displaying other_window")
        self.info(other_window)
        self.info("Performing switch to other_window")
        self.br.switch_to.window(other_window)

    def do_login(self):
        # Navigate to login page.
        self.info("Executing do_login")
        self.br.find_element_by_id("login-button").click()
        self.br.find_element_by_class_name("tp-block-half").click()
        self.br.find_element_by_class_name("other-login-button").click()
        main_window = self.br.current_window_handle
        self.info("Displaying main_window")
        self.info(main_window)
        self.main_window = self.br.current_window_handle
        self.info("Current main_window is")
        self.info(self.br.current_url)

        # Enter email.
        self.info("  Sending username.")
        email = self.br.find_element_by_css_selector(".controls input[type='text']")
        email.send_keys(input("Enter email: "))

        # Enter password.
        self.info("  Sending password.")
        passwd = self.br.find_element_by_css_selector(".controls input[type='password']")
        passwd.send_keys(input("Enter password: "))

        # Click "submit".
        self.info("Sleeping 2 seconds.")
        self.sleep(minsleep=2)
        self.info("Clicking 'sumbit' button.")
        self.br.find_element_by_css_selector(".tp-left-contents .btn-primary").click()
        self.sleep(minsleep=2)
        self.info("New url")
        self.info(self.br.current_url)

    def do_google_login(self):
        # Navigate to login page.
        self.info("Executing do_google_login")
        self.br.find_element_by_id("login-button").click()
        self.br.find_element_by_class_name("tp-block-half").click()
        self.main_window = self.br.current_window_handle

        for element in self.br.find_elements_by_tag_name("img"):
            if "btn-google.png" in element.get_attribute("src"):
                self.info(element)
                self.info("Clicking Google Button.")
                element.click()

        #self.info(self.br.find_element_by_xpath('//img[@data-bind="click:loginGoogle"]').get_attribute('innerHTML'))
        #self.br.find_element_by_class_name("other-login-button").click()

        # Sleeping really quick.
        self.info("Sleeping 2 seconds.")
        self.sleep(minsleep=2)

        # Focus on the google auth popup.
        self.switch_windows()

        # Enter email.
        email = self.br.find_element_by_id("identifierId")
        email.send_keys(input("Enter email: "))
        #email.submit()
        self.br.find_element_by_id("identifierNext").click()

        self.info("Sleeping 5 seconds.")
        self.sleep(minsleep=5)

        # Enter password.
        password = self.br.find_element_by_css_selector("input[type=password]")
        password.send_keys(getpass("Enter password:"))
        #password.submit()
        self.br.find_element_by_id("passwordNext").click()

        self.info("Sleeping 2 seconds.")
        self.sleep(minsleep=2)

        # 2FA can hopefully be handled by push notification on modern phones/apps
        self.info("Sleeping 5 seconds.")
        self.sleep(minsleep=5)

        # Switch back to tadpoles
        self.info("Switching back to main_window")
        self.br.switch_to.window(self.main_window)

    def iter_monthyear(self):
        '''Yields pairs of xpaths for each year/month tile on the
        right hand side of the user's home page.
        '''
        self.info("Executing iter_monthyear")
        month_xpath_tmpl = '//*[@id="app"]/div[3]/div[1]/ul/li[%d]/div/div/div/div/span[%d]'
        month_index = 1
        #self.info("The month_xpath_tmpl is {}".format(month_xpath_tmpl))
        #self.info("The month_index is {}".format(month_index))
        while True:
            month_xpath = month_xpath_tmpl % (month_index, 1)
            year_xpath = month_xpath_tmpl % (month_index, 2)
            #self.info("The month_xpath is {}".format(month_xpath))
            #self.info("The year_xpath is {}".format(year_xpath))

            # Go home if not there already.
            if self.br.current_url != self.HOME_URL:
                self.info("Navigating to {} for iter_monthyear function".format(self.HOME_URL))
                self.navigate_url(self.HOME_URL)
            try:
                # Find the next month and year elements.
                month = self.br.find_element_by_xpath(month_xpath)
                self.info("The month is {}".format(month))
                year = self.br.find_element_by_xpath(year_xpath)
                self.info("The year is {}".format(year))
            except NoSuchElementException:
                # We reached the end of months on the profile page.
                self.warning("No months left to scrape. Stopping.")
                sys.exit(0)

            self.month = month
            self.year = year
            yield month, year

            month_index += 1

    def iter_urls(self):
        '''Find all the image urls on the current page.
        '''
        # For each month on the dashboard...
        self.info("Executing iter_urls")
        for month, year in self.iter_monthyear():
            # Navigate to the next month.
            month.click()
            self.warning("Getting urls for month: %r" % month.text)
            self.sleep(minsleep=2)
            re_url = re.compile('\("([^"]+)')
            for div in self.br.find_elements_by_xpath("//div[@class='well left-panel pull-left']/ul/li/div"):
                url = re_url.search(div.get_attribute("style"))
                if not url:
                    continue
                url = url.group(1)
                url = url.replace('thumbnail=true', '')
                url = url.replace('&thumbnail=true', '')
                url = 'https://www.tadpoles.com' + url
                daymonth = div.find_element_by_xpath("./div/div[@class='header note mask']/span[@class='name']/span").text
                dayarray = daymonth.split('/')
                day = format(int(dayarray[1]), '02d')
                yield url, day

    def save_image(self, url, day):
        '''Save an image locally using requests.
        '''

        # Make the local filename.
        self.info("Executing save_image")
        _, key = url.split("key=")
        filename_parts = ['img', self.year.text, self.month.text, '%s']
        filename_base = abspath(join(*filename_parts) % key)
        filename = filename_base + '.jpg'

        # Only download if the file doesn't already exist.
        if isfile(filename):
            self.debug("Already downloaded: %s" % filename)
            return
        elif isfile(filename_base + '.png'):
            self.debug("Already downloaded: %s.png" % filename_base)
            return
        elif isfile(filename_base + '.jpeg'):
            self.debug("Already downloaded: %s.jpeg" % filename_base)
            return
        elif isfile(filename_base + '.mp4'):
            self.debug("Already downloaded: %s.mp4" % filename_base)
            return
        else:
            self.info("Saving: %s" % filename)
            self.sleep()

        # Make sure the parent dir exists.
        dr = dirname(filename)
        if not isdir(dr):
            os.makedirs(dr)
            info.self("Made directory {}".format(dr))

        # Download it with requests.
        resp = requests.get(url, cookies=self.req_cookies, stream=True)
        if resp.status_code == 200:
            with open(filename, 'wb') as f:
                for chunk in resp.iter_content(1024):
                    f.write(chunk)
        else:
            msg = 'Error (%r) downloading %r'
            raise DownloadError(msg % (resp.status_code, url))

        ## set date for exif
        months = dict(jan="01", feb="02", mar="03", apr="04", may="05", jun="06", jul="07", aug="08", sep="09", oct="10", nov="11", dec="12")
        yearmonth = self.year.text + ':' + months[self.month.text] + ':' + day + ' 12:00:00'
        ## check if the file is actually a png
        imgtype = imghdr.what(filename)
        timeNow = datetime.datetime.now()
        uniqueFileName = timeNow.strftime("%H%M%S%f")
        newFileName = os.path.abspath(os.path.join(filename_base, os.pardir)) + '/' + yearmonth.replace(':','').replace(' 120000','') + '_tadpoles_' + uniqueFileName
        # Get away from cases for each filetype and just build it for any type
        self.info("  File is a {} - renaming".format(imgtype))
        os.rename(filename, newFileName + '.' + imgtype)
        filename = newFileName + '.' + imgtype
        command = 'exiftool -overwrite_original "-AllDates=' + yearmonth + '" "' + filename + '"'
        self.info("  Adding exif: %s" % command)
        os.system(command)
        #if imgtype == 'png':
        #    self.info("  File is a png - renaming")
        #    os.rename(filename, newFileName + '.png')
        #    filename = newFileName + '.png'
        #    command = 'exiftool -overwrite_original "-AllDates=' + yearmonth + '" "' + filename + '"'
        #    self.info("  Adding exif: %s" % command)
        #    os.system(command)
        #elif imgtype == 'jpeg':
        #    self.info("  File is a jpeg - renaming")
        #    os.rename(filename, newFileName + '.jpeg')
        #    filename = newFileName + '.jpeg'
        #    command = 'exiftool -overwrite_original "-AllDates=' + yearmonth + '" "' + filename + '"'
        #    self.info("  Adding exif: %s" % command)
        #    os.system(command)
        #else:
        #    self.info("  File is a video - renaming")
        #    os.rename(filename, newFileName + '.mp4')
        #    filename = newFileName + '.mp4'
        #    command = 'exiftool -overwrite_original "-AllDates=' + yearmonth + '" "' + filename + '"'
        #    self.info("  Adding exif: %s" % command)
        #    os.system(command)

    def download_images(self):
        '''Login to tadpoles.com and download all user's images.
        '''
        self.info("Executing download_images")
        self.navigate_url(self.ROOT_URL)

        try:
            self.load_cookies()
        except FileNotFoundError:

            login_type = None
            while login_type is None:
                input_value = input("Login Type - [G]oogle or [E]mail/password: ")
                if input_value == 'G' or input_value == 'g':
                    login_type = 'google'
                    self.info("Doing Google login...")
                    self.do_google_login()
                elif input_value == "E" or input_value == "e":
                    login_type = 'email'
                    self.info("Doing Email login...")
                    self.do_login()
                else:
                    self.info("-- Invalid choice entered - please choose 'G' or 'E'")

            self.dump_cookies()
            self.load_cookies()
            self.add_cookies_to_browser()
            self.navigate_url(self.HOME_URL)
        else:
            self.add_cookies_to_browser()
            self.navigate_url(self.HOME_URL)

        # Get the cookies ready for requests lib.
        self.requestify_cookies()

        for url in self.iter_urls():
            try:
                self.save_image(url[0], url[1])
            except DownloadError as exc:
                self.exception(exc)

    def main(self):
        self.info("Executing main")
        with self as client:
            try:
                client.download_images()
            except Exception as exc:
                self.exception(exc)


def download_images():
    Client().main()


if __name__ == "__main__":
    download_images()

