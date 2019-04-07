from logging import error, warn, info, debug
import pandas as pd
import csv


class Competition(object):

    def __init__(self, field: list, team_filename: str):
        # initializes a competition from a list of golfers and a path to a team name:team members file
        self.teams = []
        with open(team_filename) as f:
            reader = csv.reader(f)
            for line in reader:
                info(f'initializing team: {line[0]}')
                self.teams.append(FantasyTeam(line[0], [player.replace('-', ' ') for player in line[1:]], field))
            info('All teams initialized')
        return


    def get_standings(self, defaults):
        return self.teams.sort(key=lambda team: team.get_score_with_defaults(defaults))




class FantasyTeam(object):

    def __init__(self, team_name: str, members: list, field: list):
        self.name = team_name
        self.players = self._get_members_from_field(members, field)

    def _get_members_from_field(self, members: list, field: list):
        # take list of players and list of identifiers to return list of references to players
        teammates = []
        for name in members:
            name_parts = name.rsplit(' ', 1)
            teammates.append(field.get_golfer_from_name(name_parts[0], name_parts[1]))
        return teammates

    def get_score_with_defaults(self, defaults):
        scores = []
        team_score = 0
        for player in self.players:
            total, penalty, rounds = player.get_score_or_default(defaults)
            # replace all non-integers with default (withdrawn, cut)
            defaulted = [score if isinstance(score, int) else defaults[i] for i, score in enumerate(rounds)]
            scores.append(defaulted)
        score_grid = pd.DataFrame(scores, columns = [str(i) for i in range(1,5)])
        for i in range(1,3):
            team_score += score_grid[str(i)].sum()
        for i in range (3, 5):
            team_score += score_grid[str(i)].nsmallest(3).sum()
        return team_score







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

        for round in self.rounds:
            round['score'] = round['strokes'] - par if round['strokes'] else None
            if round['round_number'] == raw['current_round']:
                round['score'] = raw['today']

    def get_score_or_default(self, defaults):
        scores = [round['score'] if round['score'] else 0 for round in self.rounds]

        if self.status == 'active':
            score = sum(scores)
            penalty = 0
        elif self.status == 'cut':
            score = self.rounds[0]['score'] + self.rounds[1]['score']
            scores[2] = 'cut'
            scores[3] = 'cut'
            penalty = sum(defaults[2:3])
        elif self.status == 'wd':
            # todo calculate withdrawn round
            score = 0
            scores = ['wd'] * 4
            penalty = sum(defaults)
        else:
            error(f'Unknown Player Status: {self.status}')
        return score, penalty, scores

    def get_next_tee_time(self):
        if self.status in ('cut', 'wd'):
            return None
        for round in reversed(self.rounds):
            if round['tee_time'] is not None:
                return round['tee_time']

    def get_raw_score_dict(self):
        scores_dict = {'round_' + str(i + 1): round['score'] if round['score'] else 0 for i, round in
                       enumerate(self.rounds)}
        info_dict = {'player_id': self.player_id, 'first_name': self.first_name, 'last_name': self.last_name,
                     'status': self.status}
        return {**info_dict, **scores_dict}


class Field(object):
    def __init__(self):
        self.golfers = []

    def get_golfer_from_name(self, first, last, silent = False) -> Golfer:
        for player in self.golfers:
            if player.first_name.lower() == first.lower() and player.last_name.lower() == last.lower():
                return player
        if not silent:
            error(f"unable to find player: {first} {last}")
        return

    def upsert_golfer(self, player_info):
        player= self.get_golfer_from_name(player_info['player_bio']['first_name'],
                                           player_info['player_bio']['last_name'], silent=True)
        if player:
            player.update(player_info, self.par)
        else:
            self.golfers.append(Golfer(player_info, self.par))
        return player
