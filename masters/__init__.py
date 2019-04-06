import logging
from masters.livedata import PGADataExtractor
from masters.models import  Competition

TEAMS_CSV = 'BOGUS_TEAMS.csv'

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
    comp = Competition(TEAMS_CSV, pga_extractor.field)
    return


if __name__ == '__main__':
    logging.basicConfig(level='DEBUG', format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')
    #dosetup
    #api.run()
    app()