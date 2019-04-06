import logging
from masters.livedata import PGADataExtractor
def app() -> None:
    pga_extractor = PGADataExtractor()







if __name__ == '__main__':
    logging.basicConfig(level='DEBUG', format='%(asctime)s - %(message)s', datefmt='%d-%b-%y %H:%M:%S')
    #dosetup
    #api.run()
    app()