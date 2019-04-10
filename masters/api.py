import responder
import logging
from masters.livedata import PGADataExtractor
from masters.models import Competition
from threading import Thread, Lock

TEAMS_CSV = 'teams.csv'
TEAMS_CSV = 'test_teams.csv'

'''
    general architecture:
    
    PGADataExtractor: contains a list of Golfers (field), a dataframe of the raw scores, and a list of the default scores
    Competition: contains set of fantasy teams
    FantasyTeam:  list of golfers, other members for getting scores etc.
    Golfer: Individual player (round info)
    
    app setup:
    startup PGA Data Extractor
    Initialize competition (initializes teams)
    Initialize API
    periodically refresh the PGA data extractor
    
'''

refresh_mutex = Lock()
api = responder.API()
pga_extractor = PGADataExtractor(refresh_mutex)
comp = Competition(pga_extractor.field, TEAMS_CSV, pga_extractor.defaults)


@api.route('/')
def greet_world(req, resp):
    refresh_mutex.acquire()
    # resp.text = f'Standings as of {pga_extractor.results_timestamp}\n'
    #
    # for team in comp.get_standings():
    #     resp.text += f'{team.name} {team.get_score_with_defaults()}\n'
    resp.html = api.template('index.html', pga_extractor=pga_extractor, comp=comp)
    refresh_mutex.release()


def app() -> None:
    data_update_thread = Thread(target=pga_extractor.start)
    data_update_thread.start()
    api.run(address='0.0.0.0', port=80)
    data_update_thread.join()
    return


if __name__ == '__main__':
    logging.basicConfig(level='DEBUG', format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')
    app()
