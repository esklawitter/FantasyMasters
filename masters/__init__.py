import logging
from masters.livedata import PGADataExtractor
from masters.models import  Competition

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
def app() -> None:
    pga_extractor = PGADataExtractor()
    pga_extractor.refresh(force=True)
    comp = Competition(pga_extractor.field, TEAMS_CSV)
    comp.get_standings(pga_extractor.defaults)
    return


if __name__ == '__main__':
    logging.basicConfig(level='DEBUG', format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')
    #dosetup
    #api.run()
    app()