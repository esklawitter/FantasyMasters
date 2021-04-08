import datetime
import json
import logging
import time
from collections import namedtuple

import math
import pandas as pd
import requests
from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

from masters.models import Field

logger = logging.getLogger(__name__)

URL_PUBLIC_LEADERBOARD = 'https://www.pgatour.com/leaderboard.html'
# TODO add TID and tour year resolution
URL_CURRENT_TID = 'https://statdata.pgatour.com/r/current/message.json'
URL_LEADERBOARD = 'https://lbdata.pgatour.com/2021/r/{}/leaderboard.json?userTrackingId={}'
URL_COURSE_INFO = 'https://www.pgatour.com/content/dam/pgatour/json/tournament/course.json'
MAX_SCORE = 9999999

CourseInfo = namedtuple('CourseInfo', ['name', 'par', 'holes'])
Hole = namedtuple('Hole', ['number', 'par', 'yards', 'description'])


class PGADataExtractor(object):
    def __init__(self, refresh_lock, tid: str = None, refresh_freq: int = 30) -> None:
        self.refresh_lock = refresh_lock
        self.course_info = self.get_course_info()
        self.field = Field(self.course_info.par)
        self.defaults = [0, 0, 0, 0]
        self.tid = '536'  # tid
        if self.tid is None:
            self.tid = self._get_active_tid()

        self._last_refresh = datetime.datetime.now()
        self.refresh_freq = refresh_freq
        self._initialize_selenium()
        self._refresh_token()
        time.sleep(3)
        self.refresh(force=True)

        logger.info(f'PGADataExtractor initialized with TID: {self.tid}')

    def start(self):
        while (True):
            self.refresh(force=True)
            time.sleep(self.refresh_freq)

    def refresh(self, force=False) -> dict:
        if force or (datetime.datetime.now() - self._last_refresh).total_seconds / 60.0 > self.refresh_freq:
            logger.debug('Refreshing leaderboard')
            self.refresh_lock.acquire()
            response = self._pull_score_data()
            self._last_refresh = datetime.datetime.now()
            self.results_timestamp = datetime.datetime.strptime(response['header']['lastUpdated'], '%Y-%m-%dT%H:%M:%S')
            logger.debug('Score timestamp is {}'.format(self.results_timestamp.strftime('%Y-%m-%dT%H:%M:%S')))
            logger.debug('Parsing leaderboard')
            self.cut_line = response['cutLines'][0]['cut_line_score']

            self.raw_leaderboard = self._compose_raw_board(response)
            self._calculate_defaults(self.raw_leaderboard)
            self.refresh_lock.release()
            logger.debug('Done parsing leaderboard')
            return

    def _calculate_defaults(self, leaderboard: pd.DataFrame):
        pre_cut = leaderboard.loc[leaderboard['status'].isin(['active', 'cut'])]
        self.defaults[0] = math.ceil(pre_cut.nlargest(5, 'round_1')['round_1'].mean())
        self.defaults[1] = math.ceil(pre_cut.nlargest(5, 'round_2')['round_2'].mean())

        post_cut = leaderboard.loc[leaderboard['status'] == 'active']
        self.defaults[2] = math.ceil(post_cut.nlargest(5, 'round_3')['round_3'].mean())
        self.defaults[3] = math.ceil(post_cut.nlargest(5, 'round_4')['round_4'].mean())

    def _compose_raw_board(self, board: dict) -> pd.DataFrame:
        '''
            takes the raw PGA dict and returns a non-normalize pandas dataframe of palyer info & round scores/storkes
        :param board: dict of raw pga data
        :return: dataframe of rows
        '''
        parsed = pd.DataFrame()
        players = []
        for player_data in board['rows']:
            self.field.upsert_golfer(player_data)
        raw_board = pd.DataFrame([p.get_raw_score_dict() for p in self.field.golfers],
                                 columns=['player_id', 'first_name', 'last_name', 'status'] + ['round_' + str(i) for i
                                                                                               in range(1, 5)])
        return raw_board
        # for each player, push all rounds, normalized to par
        # then update with current round info

    def _pull_score_data(self) -> dict:
        try:
            response = self._do_get_request(URL_LEADERBOARD.format(self.tid, self.latest_token))
            return response.json()
        except Exception as e:
            logger.debug('Token expired.')
            self._refresh_token()
            return self._pull_score_data()

    def _get_active_tid(self) -> str:
        response = self._do_get_request(URL_CURRENT_TID)
        tid = response.json()['tid']
        logger.info(f'Active TID: {tid}')
        return tid

    def _do_get_request(self, url: str) -> object:
        logger.debug(f'Get request to: {url}')
        response = requests.get(url)
        response.raise_for_status()
        return response

    def _initialize_selenium(self):
        caps = DesiredCapabilities.CHROME
        caps['goog:loggingPrefs'] = {'performance': 'ALL'}
        self.driver = webdriver.Chrome(desired_capabilities=caps)

    def _refresh_token(self) -> str:
        logger.debug('Refreshing token')
        self.driver.get(URL_PUBLIC_LEADERBOARD)
        browser_log = self.driver.get_log('performance')
        events = [json.loads(entry['message'])['message'] for entry in browser_log]
        refreshed = False
        for event in events:
            if 'Network.response' in event['method']:
                try:
                    url = event['params']['response']['url']
                    if 'userTrackingId' in url:
                        self.latest_token = url.split('userTrackingId=')[1]
                        refreshed = True
                except KeyError:
                    pass
        if not refreshed:
            logger.warn('Token refresh failed')
            time.sleep(1)
            self._refresh_token()

    def get_course_info(self) -> CourseInfo:
        # Todo this is broken, need to infer par
        course_info = self._do_get_request(URL_COURSE_INFO).json()['courses'][0]
        holes = [Hole(int(hole['number']), int(hole['parValue']), int(hole['yards']), hole['body']) for hole in
                 course_info['holes']]
        course_info = CourseInfo(course_info['name'], 72,  # int(course_info['parValue']),
                                 holes)
        logger.debug(f'Course Name: {course_info.name}. Par: {course_info.par}.')
        return course_info
