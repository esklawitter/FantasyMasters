import argparse
import logging
import sys
from threading import Thread, Lock
import masters.util as util

import responder

from masters.livedata import PGADataExtractor
from masters.models import Competition

TEAMS_CSV = 'teams/teams_masters_2020.csv'

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
jinja_formatter = util.JinjaFormatter()


@api.route('/')
def homepage(req, resp):
    refresh_mutex.acquire()
    comp.get_standings()
    resp.html = api.template('index.html', pga_extractor=pga_extractor, comp=comp, fmt=jinja_formatter)
    refresh_mutex.release()


@api.route('/prop.html')
def prop_bets(req, resp):
    refresh_mutex.acquire()
    comp.get_standings()
    resp.html = api.template('prop.html', pga_extractor=pga_extractor, comp=comp, util=util)
    refresh_mutex.release()


def app(port) -> None:
    global pga_extractor
    global comp
    pga_extractor = PGADataExtractor(refresh_mutex)  # , tid='041')
    comp = Competition(pga_extractor.field, TEAMS_CSV, pga_extractor.defaults)
    data_update_thread = Thread(target=pga_extractor.start)
    data_update_thread.start()
    api.run(address='0.0.0.0', port=port)
    data_update_thread.join()
    return


def set_up_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.WARNING)
    logging.getLogger('masters').setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter('%(asctime)s [%(levelname)7s] [%(name)20s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    root.addHandler(handler)
    logging.debug('Logging Initialized')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    set_up_logging()
    app(args.port)
