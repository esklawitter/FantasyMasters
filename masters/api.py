import logging
import sys
from threading import Thread, Lock

import responder

from masters.livedata import PGADataExtractor
from masters.models import Competition

TEAMS_CSV = 'test_teams.csv'
# TEAMS_CSV = 'test_teams.csv'

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
pga_extractor = None
comp = None


@api.route('/')
def greet_world(req, resp):
    refresh_mutex.acquire()
    comp.get_standings()
    resp.html = api.template('index.html', pga_extractor=pga_extractor, comp=comp)
    refresh_mutex.release()


def app() -> None:
    global pga_extractor
    global comp
    pga_extractor = PGADataExtractor(refresh_mutex)  # , tid='041')
    comp = Competition(pga_extractor.field, TEAMS_CSV, pga_extractor.defaults)
    data_update_thread = Thread(target=pga_extractor.start)
    data_update_thread.start()
    api.run(address='0.0.0.0', port=2577)
    data_update_thread.join()
    return


def set_up_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    root.addHandler(handler)
    logging.debug('Logging Initialized')


if __name__ == '__main__':
    set_up_logging()
    app()
