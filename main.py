import os
import re
import time
import configparser
from datetime import date
from typing import NewType

import requests
import pandas as pd

from utils import Logger

JSON_DATA = NewType("JSON_DATA", dict[str, str|list[dict[str, str]]])

PAYLOAD = {"FilterByJobSite": "",
           "FilterByAgency": "",
           "FilterByPosition": "",
           "FilterByPrincipal": "",
           "page": "1",
           "PageSize": 25}

HEADERS = {
    "Accept": "application/json",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type": "application/json",
    "Dnt": "1",
    "Origin": "https://www.dmw.gov.ph",
    "Referer": "https://www.dmw.gov.ph/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode":   "cors",
    "Sec-Fetch-Site": "same-site",
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest"
}

CONFIG = configparser.ConfigParser()

with open("./settings/settings.ini", "r") as file:
    CONFIG.read_file(file)

OUTPUT_PATH = CONFIG.get("filePaths", "output")

LOGS_PATH = CONFIG.get("filePaths", "logs")

class DMWScraper:
    """Scrapes approved job orders for licensed recruitment agencies"""
    def __init__(self) -> None:
        self.logger = Logger(LOGS_PATH, __class__.__name__)
        self.logger.info("*****DMWScraper started*****")

        self.jobs: list[dict[str, str]] = []
        self.base_url = "https://apps.dmw.gov.ph/wcms/api/job-orders"

    def __fetch_json(self) -> JSON_DATA:
        """Fetches json containing jobs from DMW"""
        while True:
            try:
                response = requests.post(
                    self.base_url, data=PAYLOAD, headers=HEADERS, timeout=30)
                
                if response.ok:
                    return response.json()

            except:pass

            time.sleep(4)

            self.logger.warn("Couldn't fetch jobs from "
                             "{}. Retrying...".format(PAYLOAD["page"]))

    def __extract_json(self, 
                       data: JSON_DATA) -> tuple[int]:
        """Extracts jobs returned from the server"""
        self.jobs.extend(data["data"])

        current_page = data["current_page"]

        last_page = data["last_page"]

        args = (len(self.jobs), current_page, last_page)

        self.logger.info(
            "Jobs extracted: {} || Current page: {}/{}".format(*args))
        
        return current_page, last_page

    def __map_to_columns(self) -> list[dict[str, str]]:
        """Maps data retrieved to appropriate columns"""
        jobs = []

        for job in self.jobs:
            jobs.append({
                "JOBSITE": job.get("JOBSITE"),
                "AGENCY": job.get("AGENCY"),
                "PRINCIPAL": job.get("PRINCIPALNAME"),
                "JO CLASS": job.get("AccreditationClass"),
                "POSITION": job.get("POSITION"),
                "JO BALANCE": job.get("JOBALANCE"),
                "DATE APPROVED": job.get("DATEAPPROVED"),
                "DATA AS OF": job.get("DATAASOF")
            })
        
        return jobs

    def __save_to_csv(self) -> None:
        """Saves data retrieved to csv"""
        self.logger.info("Saving data to csv...")

        if not os.path.exists(OUTPUT_PATH):
            os.makedirs(OUTPUT_PATH)

        final_jobs = self.__map_to_columns()

        df = pd.DataFrame(final_jobs).drop_duplicates()

        df.to_csv(f"{OUTPUT_PATH}jobs_{date.today()}.csv", index=False)

        self.logger.info("Records saved to >> {}".format(
            f"jobs_{date.today()}.csv"))

    def scrape(self) -> None:
        """Entry point to the scraper"""
        page = "1"

        while True:
            self.logger.info("Fetching jobs from page {}".format(page))

            PAYLOAD["page"] = str(page)

            jobs = self.__fetch_json()

            current_page, last_page = self.__extract_json(jobs)

            if current_page % 10 == 0 or current_page == last_page:
                self.__save_to_csv()

                if current_page == last_page:
                    self.logger.info("Done scraping!")
                    return

            next_page_url: str = jobs["next_page_url"]

            self.base_url = next_page_url

            page = re.search(r"\d+", next_page_url).group()

if __name__ == "__main__":
    scrapper = DMWScraper()
    scrapper.scrape()