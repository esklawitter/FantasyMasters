import requests
import datetime
import dataset
from logging import debug, info, warn, error

URL_CURRENT_TID = 'https://statdata.pgatour.com/r/current/message.json'
URL_LEADERBOARD = 'https://statdata.pgatour.com/r/{}/leaderboard-v2mini.json'

MAX_SCORE = 9999999

class PGADataExtractor(object):
    def __init__(self, conn_str: str, tid: str = None, refresh_freq: int = 1) -> None:
        self._init = False
        self.db = self._init_db(conn_str)

        self.tid = tid
        if self.tid is None:
            self.tid = self._get_active_tid()

        self._last_refresh = datetime.datetime.now()
        self.refresh_freq = refresh_freq
        self.refresh(force=True)

        info(f'PGADataExtractor initialized with TID: {self.tid}')

    def _init_db(self, conn_str):
        db = dataset.connect(conn_str)
        #db = dataset.connect()
        db['tbPlayer'].drop()
        db['tbRound'].drop()
        #db.get_table('tbPlayer', primary_id='player_id', primary_type=db.types.integer )
        db['tbPlayer'].create_column('player_id', db.types.integer)
        db['tbPlayer'].create_column('status', db.types.string)
        db['tbPlayer'].create_column('first_name', db.types.string)
        db['tbPlayer'].create_column('last_name', db.types.string)
        #db.get_table('tbRound', primary_id='round_id', primary_type=db.types.integer)
        db['tbRound'].create_column('round_id', db.types.integer)
        db['tbRound'].create_column('player_id', db.types.integer)
        db['tbRound'].create_column('round_num', db.types.integer)
        db['tbRound'].create_column('score', db.types.integer)
        db['tbRound'].create_column('thru', db.types.integer)
        db['tbRound'].create_column('tee_time', db.types.datetime)
        return db

    def refresh(self, force=False) -> dict:
        if force or (datetime.datetime.now() - self._last_refresh).total_seconds / 60.0 > self.refresh_freq:
            response = self._pull_score_data()
            self._last_refresh = datetime.datetime.now()
            self._results_timestamp = datetime.datetime.strptime(response['time_stamp'], '%Y%m%d%H%M%S')
            debug('score timestamp is {}'.format(self._results_timestamp.strftime('%Y-%m-%d %H:%M:%S')))
            debug('parsing leaderboard')
            board = response['leaderboard']
            self._par = int(board['courses'][0]['par_total'])
            debug('beginning player update')
            self.db.begin()
            for player in board['players']:
                player['player_id'] = int(player['player_id'])
                self._update_player(player)
            self.db.commit()
            debug('ended player update')
            self._init = True
            return

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

    def _update_player(self, player_info: dict):
        # update player info
        player_id = player_info['player_id']
        self._upsert_player(player_id, player_info['status'], player_info['player_bio'])
        # update rounds
        self._update_rounds(player_id, player_info)

    def _update_rounds(self, player_id, player_info):
        # goal is persist score, thru, teetime
        rounds = player_info['rounds']
        cur_round = player_info['current_round']

        # if player withdrew, negate all rounds including last
        if player_info['status'] == 'wd':
            for round in reversed(rounds):
                if round['strokes']:
                    round['strokes'] = MAX_SCORE
                    break
                round['strokes'] = MAX_SCORE
        if player_info['status'] == 'cut':
            rounds[2]['strokes'] = MAX_SCORE
            rounds[3]['strokes'] = MAX_SCORE

        for round in player_info['rounds']:
            round_num = round['round_number']
            strokes = round['strokes']
            tee_string = round['tee_time']
            tee_time = datetime.datetime.strptime(tee_string,'%Y-%m-%dT%X')  if tee_string else None
            score = round['strokes']
            thru = None
            if round['round_number'] == cur_round:
                thru = player_info['thru']
                score = player_info['today']
            elif strokes not in (MAX_SCORE, None):
                score = round['strokes'] - self._par
                thru = 18
            # if cur round, need to be careful about thru
            self._upsert_round(player_id, round_num, score, thru, tee_time)

    def _upsert_round(self, player_id: int, round_num: int, score: int, thru: int, tee_time: datetime):
        rec = {
            'round_id': player_id * 100000 + round_num,
            'player_id': player_id,
            'round_num': round_num,
            'score': score,
            'thru': thru,
            'tee_time': tee_time
        }
        self.db['tbRound'].upsert(rec, ['round_id'])

    def _upsert_player(self, player_id: int, status: str, player_bio: dict):
        rec = {'player_id': player_id,
               'status': status,
               'first_name': player_bio['first_name'],
               'last_name': player_bio['last_name']}
        self.db['tbPlayer'].upsert(rec, 'player_id')
