import csv
from logging import error, info

import pandas as pd

TEAM_SIZE = 6
WEEKEND_TEAM_SIZE = 4
SATURDAY_ROUND = 3


def str_to_int(val: str, none_is_zero=True):
    # convenience function to strip down to raw integer
    digits = ''.join(c for c in val if c.isdigit())
    if digits:
        return int(digits)
    else:
        if none_is_zero:
            return 0
        else:
            return None


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
                    FantasyTeam(line[0], line[1:], field, defaults))
            info('All teams initialized')
        return

    @property
    def standings(self):
        return self.get_standings()

    def get_standings(self):
        self.teams.sort(key=lambda team: team.score)
        self._calculate_positions()

        return self.teams

    def _calculate_positions(self):
        scores = [team.score for team in self.teams]
        scores_df = pd.DataFrame(scores, columns=['score'])
        grouped_scores = scores_df.groupby('score', sort=True)
        score_rank_map = {}
        ix = 1
        for score, teams in grouped_scores:
            num_teams = len(teams)
            if num_teams > 1:
                score_rank_map[score] = f'T{ix}'
            else:
                score_rank_map[score] = str(ix)
            ix += num_teams
        for team in self.teams:
            team.position = score_rank_map[team.score]
        return


class FantasyTeam(object):

    def __init__(self, team_name: str, members: list, field: list, defaults):
        self.name = team_name
        self.defaults = defaults
        self.players = self._get_members_from_field(members, field)

    @property
    def score(self):
        return self.get_score_with_defaults()[0]

    def get_pct_complete(self):
        par = 72.0 * 4  # todo resolve this
        total = 0
        for player in self.players:
            if player.is_active():
                if player.round_complete:
                    total += 18
                else:
                    total += str_to_int(player.thru)
        return total / par

    def get_pct_complete_str(self, width=0):
        res = f'{self.get_pct_complete():10.0%}'
        return ' ' * (width - len(res)) + res

    def _get_members_from_field(self, members: list, field: list):
        # take list of players and list of identifiers to return list of references to players
        teammates = []
        for name in members:
            name_parts = name.split(' ', 1) if name != 'Byeong Hun An' else ['Byeong Hun', 'An']
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

        for round_num in range(1, 5):
            scores.sort(
                key=lambda x: x[round_num]['score'])  # this is ugly because player is the first item in the array
            for player_ix in range(TEAM_SIZE if round_num < SATURDAY_ROUND else WEEKEND_TEAM_SIZE):
                daily_scores[round_num - 1] += scores[player_ix][round_num]['score']
                scores[player_ix][round_num]['counted'] = True
            team_score += daily_scores[round_num - 1]
        return team_score, scores, daily_scores

    def get_scores_df(self) -> pd.DataFrame:
        return pd.DataFrame([golfer.get_raw_score_dict() for golfer in self.players])

    def add_plus(self, score: int):
        return f'+{score}' if score >= 0 else f'{score}'


class Golfer(object):

    def __init__(self, raw, par):
        '''
         creates a player from raw player data
        '''
        self.update(raw, par)

    def update(self, raw, par):
        self.player_id = raw['playerId']
        self.first_name = raw['playerNames']['firstName']
        self.last_name = raw['playerNames']['lastName']

        self.status = raw['status']

        self.rounds = raw['rounds']
        self.thru = raw['thru'] if raw['thru'] != '' else None
        self.tee_time = raw['teeTime']
        self.position = raw['positionCurrent']
        self.round_complete = raw['roundComplete']
        raw_rank = raw['projectedRanks']['cupRank']
        self.rank = raw_rank if raw_rank else None

        for round in self.rounds:
            round['score'] = int(round['strokes']) - par if round['strokes'] != '--' else None
            if self._round_title_to_int(round['title']) == raw[
                'tournamentRoundId']:  # Todo: confirm that tournamentRoundId works as expected
                round['score'] = raw['today']

    def _round_title_to_int(self, round: str) -> int:
        return int(round.replace('r', ''))

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
        if not self.is_active():
            return None
        return self.tee_time  # todo figure out how this works with the new api

    def get_today(self):
        if self.is_active():
            return self.thru
        else:
            return 'NA'

    def is_active(self):
        if self.status.lower() in ('cut', 'wd'):
            return False
        else:
            return True

    def get_raw_score_dict(self):
        scores_dict = {'round_' + str(i + 1): round['score'] if round['score'] else 0 for i, round in
                       enumerate(self.rounds)}
        info_dict = {'player_id': self.player_id, 'first_name': self.first_name, 'last_name': self.last_name,
                     'status': self.status}
        return {**info_dict, **scores_dict}


class Field(object):
    def __init__(self, par):
        self.par = par
        self.golfers = []

    def get_golfer_from_name(self, first, last, silent=False) -> Golfer:
        for player in self.golfers:
            if player.first_name.lower() == first.lower() and player.last_name.lower() == last.lower():
                return player
        if not silent:
            error(f"Unable to find player: {first} {last}")
        return

    def upsert_golfer(self, player_info):
        player = self.get_golfer_from_name(player_info['playerNames']['firstName'],
                                           player_info['playerNames']['lastName'], silent=True)
        if player:
            player.update(player_info, self.par)
        else:
            player = Golfer(player_info, self.par)
            self.golfers.append(player)
        return player
