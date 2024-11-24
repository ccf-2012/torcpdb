import configparser
import os


class configData():
    tmdb_api_key = ''
    tmdb_lang = 'zh_CN'

CONFIG = configData()


def readConfig(cfgFile):
    config = configparser.ConfigParser()
    config.read(cfgFile)

    if 'TMDB' in config:
        CONFIG.tmdb_api_key = config['TMDB'].get('tmdb_api_key', '')
        CONFIG.tmdb_lang = config['TMDB'].get('tmdb_lang', 'zh_CN')

