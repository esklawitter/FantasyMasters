import requests
import datetime
import pandas as pd
from masters.models import Golfer, Field
import copy
from logging import debug, info, warn, error
import math
import time

URL_CURRENT_TID = 'https://statdata.pgatour.com/r/current/message.json'
URL_LEADERBOARD = 'https://statdata.pgatour.com/r/{}/leaderboard-v2mini.json'

MAX_SCORE = 9999999


class PGADataExtractor(object):
    def __init__(self, refresh_lock, tid: str = None, refresh_freq: int = 10) -> None:
        self.refresh_lock = refresh_lock
        self.field = Field()
        self.defaults = [0, 0, 0, 0]
        self.tid = tid
        if self.tid is None:
            self.tid = self._get_active_tid()

        self._last_refresh = datetime.datetime.now()
        self.refresh_freq = refresh_freq
        self.refresh(force=True)

        info(f'PGADataExtractor initialized with TID: {self.tid}')

    def start(self):
        while (True):
            self.refresh(force=True)
            time.sleep(self.refresh_freq)

    def refresh(self, force=False) -> dict:
        if force or (datetime.datetime.now() - self._last_refresh).total_seconds / 60.0 > self.refresh_freq:
            self.refresh_lock.acquire()
            response = self._pull_score_data()
            self._last_refresh = datetime.datetime.now()
            self.results_timestamp = datetime.datetime.strptime(response['time_stamp'], '%Y%m%d%H%M%S')
            debug('score timestamp is {}'.format(self.results_timestamp.strftime('%Y-%m-%d %H:%M:%S')))
            debug('parsing leaderboard')

            if self.field.par is None:
                par = int(response['leaderboard']['courses'][0]['par_total'])
                info(f'Setting field par to: {par}')
                self.field.par = par

            self.raw_leaderboard = self._compose_raw_board(response['leaderboard'])
            self._calculate_defaults(self.raw_leaderboard)
            self.refresh_lock.release()
            debug('done parsing leaderboard')
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
        for player_data in board['players']:
            self.field.upsert_golfer(player_data)
        raw_board = pd.DataFrame([p.get_raw_score_dict() for p in self.field.golfers], columns=['player_id', 'first_name', 'last_name', 'status'] + ['round_' + str(i) for i in range(1,5)])
        return raw_board
        # for each player, push all rounds, normalized to par
        # then update with current round info

    def _pull_score_data(self) -> dict:
        response = self._do_get_request(URL_LEADERBOARD.format(self.tid))
        return response.json()

    def _get_active_tid(self) -> str:
        response = self._do_get_request(URL_CURRENT_TID)
        tid = response.json()['tid']
        info(f'Active TID: {tid}')
        return tid

    def _do_get_request(self, url: str) -> object:
        debug(f'get request to: {url}')
        response = requests.get(url)
        debug(f'received status code: {response.status_code}')
        return response
