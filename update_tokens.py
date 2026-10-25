import sys  # to provide access to Python interpreter's state and behaviour, e.g. sys.exit, sys.version (provides Python's version) 

# where else to look for to find the files needed for this program. 
sys.path.append("/Users/apple/Documents/Programming/update_kite_tokens")

import pytz, pyotp, requests, time
from email.utils import parsedate_to_datetime

from datetime import datetime, time as t, timedelta
from kiteconnect import KiteConnect
from playwright.sync_api import sync_playwright
from playwright._impl._errors import TimeoutError
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from urllib.parse import urlparse, parse_qs

new_request_token = None

class CallbackHandler(BaseHTTPRequestHandler):

    def do_GET(self):


        global new_request_token

        # parse the callback url
        parsed_url = urlparse(self.path)

        # extract query parameters from the url
        query_params = parse_qs(parsed_url.query)

        # save the request token if present
        if "request_token" in query_params:

            new_request_token = query_params["request_token"][0]

        # send a successful http response
        self.send_response(200)

        self.end_headers()

        # display a success message in the browser
        self.wfile.write(b"Login successful")

    # suppress default http request logging
    # The default logging looks something like this:
    # 127.0.0.1 - - [12/Jul/2026 14:32:15] "GET /?request_token=abc123 HTTP/1.1" 200 -
    def log_message(self, format, *args):

        pass


def fetch_request_token(credentials=None):

    """create a new request token and store it in keys.txt"""

    global new_request_token

    # reset the global request token before starting a new login
    new_request_token = None

    # load credentials if none were provided
    if credentials is None:
        credentials = fetch_user_credentials()


    HTTPServer.allow_reuse_address = True

    # create HTTP server object
    # HTTPServer is a class from http.server module, 
    # HTTPServer is used to listen to incoming http requests and pass them onto a CallbackHandler

    # (localhost, 8000) configures where the HTTPServer should listen for these requests
    # localhost is our machine with the IP address 127.0.0.1
    # (localhost, 8000) = ("127.0.0.1, 8000") 

    # CallbackHandler is the class we defined to handle https requests
    # a callback is a function or method that someone else calls when an event occurs
    # e.g. we never call do_GET() ourselves. HTTPServer automatically creates an instance of CallbackHandler 
    # and calls its do_GET() method whenever it receives a GET request.
    # we need a callback function and callbackHandler because we cannot know beforehand when a request arrives

    # HTTP request flow: while we are logging in, our browser sends HTTP requests to Zerodha's servers.
    # after successful authentication, Zerodha sends an HTTP redirect response containing
    # the request_token URL. our browser follows that redirect by sending an HTTP GET
    # request to our local HTTPServer.
    # this is done so the python program can receive the url containing the request_token
    # through the local server, since it cannot directly communicate with the browser.
    # In return, the HTTPServer returns a simple response shown in do_GET()

    server = HTTPServer(("localhost", 8000), CallbackHandler)

    # run the callback server in a background thread
    # threading is the ability of a program to run multiple processes simultaneously

    # Main thread                  Background thread
    # -----------                  -----------------
    # Run Playwright               Run HTTP server
    # Fill login form              Wait for requests
    #Wait for request token        Process callback

    # “Run the HTTP server in the background. If the main program exits, 
    # don’t wait for the server thread—terminate it automatically.”
    # If it were daemon=False (the default), Python would wait for that thread to finish before exiting.

    Thread(
        target=server.serve_forever,
        daemon=True
    ).start()

    api_key = credentials["api_key"]
    totp_secret = credentials["totp_secret"]
    totp = pyotp.TOTP(totp_secret)
    kite_username = credentials["kite_username"]
    kite_password = credentials["kite_password"]

    with sync_playwright() as p:

        # launch a headless chromium browser
        browser = p.chromium.launch(headless=True)

        page = browser.new_page()

        # open the zerodha login page
        page.goto(
            f"https://kite.zerodha.com/connect/login?api_key={api_key}&v=3"
        )

        # locate the username input field
        username = page.get_by_role(
            "textbox",
            name="Phone number or User ID"
        )

        # locate the password input field
        password = page.get_by_role(
            "textbox",
            name="Password"
        )

        # enter login credentials
        username.fill(kite_username)
        password.fill(kite_password)

        # locate and click the login button
        login_button = page.get_by_role(
            "button",
            name="Login"
        )

        login_button.click()

        # locate the totp input field
        totp_textbox = page.get_by_role(
            "spinbutton",
            name="External TOTP"
        )

        response = requests.get("https://www.google.com", timeout=5)

        server_time = parsedate_to_datetime(
            response.headers["Date"]
        ).timestamp()

        offset = server_time - time.time()

        code = totp.at(time.time() + offset)

        # enter the current totp code
        totp_textbox.fill(code)

        # locate the continue button
        continue_button = page.get_by_role(
            "button",
            name="Continue"

        )

        # submit the totp if the button is available
        # waits up to 1 second for the continue button to become clickable.
        try:
            continue_button.click(timeout=1)
        except TimeoutError:
            pass

        # wait for the callback server to receive the request token
        timeout = time.time() + 30

        # the callback is triggered inside this loop when the browser sends the redirected
        # http request to our local server. it isn't evident because HTTPServer is running
        # in the background, listening for requests and automatically calling CallbackHandler.do_GET().

        while new_request_token is None:
        
            # stop waiting after 30 seconds
            if time.time() > timeout:

                server.shutdown()

                raise TimeoutError(
                    "Timed out waiting for request token."
                )

            # reduce cpu usage while waiting
            time.sleep(0.1)

        # store the received request token
        credentials["request_token"] = new_request_token

        # stop the callback server
        server.shutdown()

        # save the updated credentials to disk

        with open("/Users/apple/Documents/Programming/options_analysis/common_modules/keys.txt", "w") as file:
            for key, value in credentials.items():
                file.write(f"{key}={value}\n")

        # close the browser
        browser.close()


def fetch_user_credentials():
    """read username login data from a local file."""

    credentials = {}

    with open("/Users/apple/Documents/Programming/options_analysis/common_modules/keys.txt") as file:
        # the line below works because the file object is iterable so the next line is asked repeatedly
        for line in file:
            key, value = line.strip().split("=")
            credentials[key] = value


    return credentials


def get_current_time():

    IST = pytz.timezone("Asia/Kolkata")
    current_time = datetime.now(IST).time()
    return current_time

def get_weekday():

    IST = pytz.timezone("Asia/Kolkata")
    weekday = datetime.now(IST).weekday()
    return weekday


def seconds_until_next_9am():
    """calculate how many seconds remain until 9 AM IST tomorrow"""

    IST = pytz.timezone("Asia/Kolkata")

    # get the current date+time in IST (keeping the date this time,
    # since we need to calculate tomorrow's date below)
    now_datetime = datetime.now(IST)

    # extract just today's date from now_datetime, then add one day
    # to get tomorrow's date
    tomorrow = now_datetime.date() + timedelta(days=1)

    # combine tomorrow's date with a fixed time of 9:13 AM to build
    # a full datetime representing "9:13 AM tomorrow"
    # localize() attaches the IST timezone info, since datetime.combine()
    # on its own produces a naive (timezone-unaware) datetime
    next_run = IST.localize(datetime.combine(tomorrow, t(9, 0)))

    # subtract the current datetime from tomorrow's 9:13 AM datetime
    # to get a timedelta (a duration), then convert that duration
    # into a plain number of seconds
    return (next_run - now_datetime).total_seconds()


def update_access_token(credentials=None):

    """update the access token in the txt file."""

    if credentials is None:
        credentials = fetch_user_credentials()

    # extract api secret from credentials dictionary
    api_key = credentials["api_key"]
    api_secret = credentials["api_secret"]
    request_token = credentials["request_token"]

    # initialise Kite client
    kite = KiteConnect(api_key=api_key)

    # generate session
    data = kite.generate_session(request_token=request_token, api_secret=api_secret)

    # extract new access token from the kite session data
    new_access_token = data["access_token"]

    # update tokens in the credientials dictionary
    credentials["access_token"] = new_access_token

    # update tokens in the txt file.
    with open("/Users/apple/Documents/Programming/options_analysis/common_modules/keys.txt", "w") as file:
        for key, value in credentials.items():
            file.write(f"{key}={value}\n")


def main():
    """the main workflow of the program"""

    # this loop is meant to keep the program running continuosly using PM2.
    while True:

        weekday = get_weekday()

        if weekday < 5: # weekdays

            current_time = get_current_time()

            if t(8, 0) <= current_time < t(8, 45):
                time.sleep(900)

            elif t(8, 45) <= current_time < t(9, 0):
                time.sleep(60)

            elif t(9, 0) <= current_time <= t(9, 15):

                credentials = fetch_user_credentials()

                fetch_request_token(credentials=credentials)
                update_access_token(credentials=credentials)

                time.sleep(960)

            else:
                time.sleep(3600)

if __name__ == "__main__":

    main()