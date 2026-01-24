import requests
import time
import logging
from requests.exceptions import RequestException, ConnectionError, Timeout, ReadTimeout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("mailru_checker.log", encoding='utf-8'),
        logging.StreamHandler()])
class MailRuChecker:
    def __init__(self, timeout=10):
        self.session = requests.Session()
        self.session.verify = False
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.timeout = timeout
        self.use_api_1 = True
    def check(self, email):
        try:
            if self.use_api_1:
                result = self._check_api_1(email)
            else:
                result = self._check_api_2(email)
            self.use_api_1 = not self.use_api_1
            return result
        except Exception as e:
            self.use_api_1 = not self.use_api_1
            raise e
    def _check_api_1(self, email):
        url = "https://alt-auth.mail.ru/api/v1/pushauth/info"
        params = {"mmp": "mail","mp": "android"}
        headers = {
            "Host": "alt-auth.mail.ru",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "okhttp/4.12.0"}
        data = {"sat": "false","login": email}
        return self.__make_request(url, params, headers, data, "API 1")
    def _check_api_2(self, email):
        url = "https://alt-aj-https.mail.ru/api/v1/user/exists"
        params = {
            "act_mode": "inact",
            "mp": "android",
            "mmp": "mail",
            "ver": "ru.mail.mailapp15.70.0.130771"}
        headers = {
            "User-Agent": "mobmail android 15.70.0.130771 ru.mail.mailapp",
            "Content-Type": "application/x-www-form-urlencoded",}
        data = {"email": email}
        return self.__make_request(url, params, headers, data, "API 2")
    def __make_request(self, url, params, headers, data, api_name):
        try:
            response = self.session.post(url,params=params,headers=headers,data=data,timeout=self.timeout)
            result = response.json()
            is_taken = result["body"]["exists"]
            return is_taken
        except ConnectionError as e:
            logging.error(f"CONNECTION_ERROR with api {api_name}: Failed to connect to the server - {str(e)}")
            return self.__make_request(url, params, headers, data, api_name)
        except Timeout as e:
            logging.error(f"TIMEOUT_ERROR with api {api_name}: Request timed out - {str(e)}")
            return self.__make_request(url, params, headers, data, api_name)
        except ReadTimeout as e:
            logging.error(f"READ_TIMEOUT_ERROR with api {api_name}: Failed to read response - {str(e)}")
            return self.__make_request(url, params, headers, data, api_name )
        except Exception as e:
            if "string indices must be integers, not 'str'" in str(e):
                logging.error(f"Unexpected JSON structure: {result}")
            logging.error(f"JSON_ERROR with api {api_name}: Failed to parse response - {str(e)}")
            raise Exception(f"JSON_ERROR with api {api_name}: Failed to parse response - {str(e)}")    