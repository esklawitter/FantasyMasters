from logging import error, warn, info, debug
import pandas as pd
import csv
import datetime


class Competition(object):

    def __init__(self, field: list, team_filename: str, defaults: list):
        # initializes a competition from a list of golfers and a path to a team name:team members file
        self.teams = []
        self.defaults = defaults
        with open(team_filename) as f:
            reader = csv.reader(f)
            for line in reader:
                info(f'initializing team: {line[0]}')
                self.teams.append(
                    FantasyTeam(line[0], [player.replace('-', ' ') for player in line[1:]], field, defaults))
            info('All teams initialized')
        return

    @property
    def standings(self):
        return self.get_standings()

    def get_standings(self):
        self.teams.sort(key=lambda team: team.score)
        return self.teams


class FantasyTeam(object):

    def __init__(self, team_name: str, members: list, field: list, defaults):
        self.name = team_name
        self.defaults = defaults
        self.players = self._get_members_from_field(members, field)

    @property
    def score(self):
        return self.get_score_with_defaults()[0]

    def _get_members_from_field(self, members: list, field: list):
        # take list of players and list of identifiers to return list of references to players
        teammates = []
        for name in members:
            name_parts = name.split(' ', 1) if name != 'Si Woo Kim' else ['Si Woo', 'Kim']
            teammates.append(field.get_golfer_from_name(name_parts[0], name_parts[1]))
        return teammates

    def get_score_with_defaults(self):
        scores = []
        team_score = 0
        daily_scores = [0, 0, 0, 0]
        for player in self.players:
            total, rounds = player.get_score_or_default()
            # replace all non-integers with default (withdrawn, cut)
            defaulted = [player] + [
                {'score': score, 'score_str': self.add_plus(score), 'undefaulted': score,
                 'undef_str': self.add_plus(score), 'counted': False, 'is_penalty': False} if isinstance(score,
                                                                                                         int) else {
                    'score': self.defaults[i], 'score_str': self.add_plus(self.defaults[i]), 'undefaulted': score,
                    'undef_str': score, 'counted': False, 'is_penalty': True} for i, score in enumerate(rounds)]
            scores.append(defaulted)

        for i in range(1, 5):
            scores.sort(key=lambda x: x[i]['score'])  # this is ugly because player is the first item in the array
            for j in range(5 if i < 3 else 3):
                daily_scores[i - 1] += scores[j][i]['score']
                scores[j][i]['counted'] = True
            team_score += daily_scores[i - 1]
        return team_score, scores, daily_scores

    def get_scores_df(self):
        return pd.DataFrame([golfer.get_raw_score_dict() for golfer in self.players])

    def add_plus(self, score):
        return f'+{score}' if score >= 0 else f'{score}'


class Golfer(object):

    def __init__(self, raw, par):
        '''
         creates a player from raw player data
        '''
        self.update(raw, par)

    def update(self, raw, par):
        self.player_id = raw['player_id']
        self.first_name = raw['player_bio']['first_name']
        self.last_name = raw['player_bio']['last_name']

        self.status = raw['status']

        self.rounds = raw['rounds']
        self.thru = raw['thru']

        for round in self.rounds:
            round['score'] = round['strokes'] - par if round['strokes'] else None
            if round['round_number'] == raw['current_round']:
                round['score'] = raw['today']

    def get_score_or_default(self):
        # todo: refactor this to better align with access pattern (eg, no need for separate penalty)
        scores = [round['score'] if round['score'] else 0 for round in self.rounds]

        if self.status == 'active':
            score = sum(scores)
        elif self.status == 'cut':
            score = self.rounds[0]['score'] + self.rounds[1]['score']
            scores[2] = 'cut'
            scores[3] = 'cut'
        elif self.status == 'wd':
            # todo calculate withdrawn round
            score = 0
            scores = ['wd'] * 4
        else:
            error(f'Unknown Player Status: {self.status}')
        return score, scores

    def get_next_tee_time(self):
        if self.status in ('cut', 'wd'):
            return None
        times = []
        for round in self.rounds:
            if round['tee_time'] is not None:
                times.append(datetime.datetime.strptime(round['tee_time'], '%Y-%m-%dT%H:%M:%S'))
        return min(times)

    def get_today(self):
        if self.thru is not None and self.thru != 18:
            return self.thru
        elif self.get_next_tee_time() is not None:
            return self.get_next_tee_time().strftime('%a %I:%M%p')
        else:
            return 'NA'

    def get_raw_score_dict(self):
        scores_dict = {'round_' + str(i + 1): round['score'] if round['score'] else 0 for i, round in
                       enumerate(self.rounds)}
        info_dict = {'player_id': self.player_id, 'first_name': self.first_name, 'last_name': self.last_name,
                     'status': self.status}
        return {**info_dict, **scores_dict}


class Field(object):
    def __init__(self):
        self.par = None
        self.golfers = []

    def get_golfer_from_name(self, first, last, silent=False) -> Golfer:
        for player in self.golfers:
            if player.first_name.lower() == first.lower() and player.last_name.lower() == last.lower():
                return player
        if not silent:
            error(f"unable to find player: {first} {last}")
        return

    def upsert_golfer(self, player_info):
        player = self.get_golfer_from_name(player_info['player_bio']['first_name'],
                                           player_info['player_bio']['last_name'], silent=True)
        if player:
            player.update(player_info, self.par)
        else:
            self.golfers.append(Golfer(player_info, self.par))
        return player
