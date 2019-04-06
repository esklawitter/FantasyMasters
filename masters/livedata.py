import requests
import datetime
from logging import debug, info, warn, error

URL_CURRENT_TID = 'https://statdata.pgatour.com/r/current/message.json'
URL_LEADERBOARD = 'https://statdata.pgatour.com/r/{}/leaderboard-v2mini.json'


class PGADataExtractor(object):
    def __init__(self, tid:str=None, refresh_freq:int=1) -> None:
        self.tid = tid
        if self.tid is None:
            self.tid = self._get_active_tid()


        self._last_refresh = datetime.datetime.now()
        self.refresh_freq = refresh_freq
        self.refresh(force=True)

        info(f'PGADataExtractor initialized with TID: {self.tid}')

    def refresh(self, force=False) -> dict:
        if force or (datetime.datetime.now() - self._last_refresh).min > self.refresh_freq:
            self._scores = self._pull_score_data()
            self._last_refresh = datetime.datetime.now()

        return self._scores

    def _pull_score_data(self) -> dict:
        response = self._do_get_request(URL_LEADERBOARD.format(self.tid))
        return response.json()

    def _get_active_tid(self) -> str:
        response = self._do_get_request(URL_CURRENT_TID)
        tid = response.json()['tid']
        info(f'Active TID: {tid}')
        return tid

    def _do_get_request(self, url:str) -> object:
        debug(f'get request to: {url}')
        response = requests.get(url)
        debug(f'received status code: {response.status_code}')
        return response



