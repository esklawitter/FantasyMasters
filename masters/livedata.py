import requests
import datetime
import dataset
import pandas as pd
from masters.models import Golfer, Field
import copy
from logging import debug, info, warn, error
import math

URL_CURRENT_TID = 'https://statdata.pgatour.com/r/current/message.json'
URL_LEADERBOARD = 'https://statdata.pgatour.com/r/{}/leaderboard-v2mini.json'

MAX_SCORE = 9999999
PAR = None


class PGADataExtractor(object):
    def __init__(self, tid: str = None, refresh_freq: int = 1) -> None:
        self.field = Field()
        self.tid = tid
        if self.tid is None:
            self.tid = self._get_active_tid()

        self._last_refresh = datetime.datetime.now()
        self.refresh_freq = refresh_freq
        self.refresh(force=True)

        info(f'PGADataExtractor initialized with TID: {self.tid}')

    def refresh(self, force=False) -> dict:
        if force or (datetime.datetime.now() - self._last_refresh).total_seconds / 60.0 > self.refresh_freq:
            response = self._pull_score_data()
            self._last_refresh = datetime.datetime.now()
            self._results_timestamp = datetime.datetime.strptime(response['time_stamp'], '%Y%m%d%H%M%S')
            debug('score timestamp is {}'.format(self._results_timestamp.strftime('%Y-%m-%d %H:%M:%S')))
            debug('parsing leaderboard')

            PAR = int(response['leaderboard']['courses'][0]['par_total'])
            info(f'Setting field par to: {PAR}')
            self.field.par = PAR

            self.raw_leaderboard = self._compose_raw_board(response['leaderboard'])
            self.defaults = self._calculate_defaults(self.raw_leaderboard)
            return

    def _calculate_defaults(self, leaderboard: pd.DataFrame):
        defaults = [0, 0, 0, 0]
        pre_cut = leaderboard.loc[leaderboard['status'].isin(['active', 'cut'])]
        defaults[0] = pre_cut.nlargest(5, 'round_1')['round_1'].mean()
        defaults[1] = pre_cut.nlargest(5, 'round_2')['round_2'].mean()

        post_cut = leaderboard.loc[leaderboard['status'] == 'active']
        defaults[2] = post_cut.nlargest(5, 'round_3')['round_3'].mean()
        defaults[3] = post_cut.nlargest(5, 'round_4')['round_4'].mean()
        defaults = [math.ceil(default) for default in defaults]
        return defaults

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
        raw_board = pd.DataFrame([p.get_raw_score_dict() for p in self.field.golfers])
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
