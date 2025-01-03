import configparser
import os


class configData():
    basicAuthUser = ''
    basicAuthPass = ''
    tmdb_api_key = ''
    tmdb_lang = 'zh_CN'
    client_api_key = 'client_api_key'
    # mysql config
    mysql_host = "localhost"
    mysql_port = 3306
    mysql_user = 'torll'
    mysql_pass = 'Cr#91237'
    mysql_db = 'torll'

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

    if 'MYSQL' in config:
        CONFIG.mysql_host = config['MYSQL'].get('host', 'localhost')
        CONFIG.mysql_port = config['MYSQL'].getint('port', 3306)
        CONFIG.mysql_user = config['MYSQL'].get('user', 'torll')
        CONFIG.mysql_pass = config['MYSQL'].get('pass', 'Cr#91237')
        CONFIG.mysql_db = config['MYSQL'].get('db', 'torll')