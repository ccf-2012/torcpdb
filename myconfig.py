import configparser
import os


class configData():
    basicAuthUser = ''
    basicAuthPass = ''
    tmdb_api_key = ''
    tmdb_lang = 'zh_CN'
    client_api_key = 'client_api_key'

CONFIG = configData()


def readConfig(cfgFile):
    config = configparser.ConfigParser()
    config.read(cfgFile)

    if 'AUTH' in config:
        CONFIG.basicAuthUser = config['AUTH'].get('user', '')
        CONFIG.basicAuthPass = config['AUTH'].get('pass', '')

    if 'TMDB' in config:
        CONFIG.tmdb_api_key = config['TMDB'].get('tmdb_api_key', '')
        CONFIG.tmdb_lang = config['TMDB'].get('tmdb_lang', 'zh_CN')
    if 'AUTH' in config:
        CONFIG.client_api_key = config['AUTH'].get('client_api_key', '')

