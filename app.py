# app.py
from flask import Flask, request, jsonify, render_template, redirect, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text, literal
from sqlalchemy.orm import relationship
from datetime import datetime
import resource  # 添加 resource 模块导入

import os, sys, re
from torinfo import TorrentParser, TorrentInfo
from tmdbsearcher import TMDbSearcher
import myconfig
from loguru import logger
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
# 导入 models.py 中的定义
from models import (
    db,
    TorrentRecord,
    MediaRecord
)

app = Flask(__name__)

def loadMysqlConfig():
    app.config["MYSQL_HOST"] = myconfig.CONFIG.mysql_host
    app.config["MYSQL_PORT"] = myconfig.CONFIG.mysql_port
    app.config["MYSQL_USER"] = myconfig.CONFIG.mysql_user
    app.config["MYSQL_PASSWORD"] = myconfig.CONFIG.mysql_pass
    app.config["MYSQL_DB"] = myconfig.CONFIG.mysql_db
    app.config["SQLALCHEMY_DATABASE_URI"] = "mysql://{}:{}@{}:{}/{}".format(
        app.config["MYSQL_USER"],
        app.config["MYSQL_PASSWORD"],
        app.config["MYSQL_HOST"],
        app.config["MYSQL_PORT"],
        app.config["MYSQL_DB"],
    )
    db.init_app(app)


# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///media.db'
# app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.secret_key = 'torcp_db_key'  # 用于签名 session

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # 未登录时重定向到登录页面
login_manager.login_message = ''

# torll 用户，在 config.ini 中定义
class User(UserMixin):
    def __init__(self, username):
        self.id = username

@login_manager.user_loader
def load_user(username):
    if username == myconfig.CONFIG.basicAuthUser:
        return User(username)
    return None


# https://stackoverflow.com/questions/33106298/is-it-possible-to-use-flask-logins-authentication-as-simple-http-auth-for-a-res
@login_manager.request_loader
def load_user_from_header(request):
    # user = User('admin')
    # return user    
    auth = request.authorization
    if not auth:
        return None
    if (auth.username == myconfig.CONFIG.basicAuthUser) and (auth.password == myconfig.CONFIG.basicAuthPass):
        user = User(auth.username, remember=True)
        login_user(user, remember=True)  # 登录用户
        return user
    else:
        abort(401)


@app.route('/login', methods=['GET', 'POST'])
def login():
    # if current_user.is_authenticated:
    #     return redirect('/')
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == myconfig.CONFIG.basicAuthUser and password == myconfig.CONFIG.basicAuthPass:
            user = User(username)
            login_user(user, remember=True)  # 登录用户
            # logger.success(f'{username } 登陆成功')
            return redirect('/')  # 登录成功后重定向到首页
        else:
            # logger.success(f'{username } 密码错误')
            return '密码错误，请重试.'
    return render_template('login.html')

@app.route('/logout')
def logout():
    logout_user()  # 注销用户
    return redirect('/login')



from functools import wraps

def abortjson():
    return jsonify({
                'error': 'Invalid or missing API key',
                'status': 'unauthorized'
            }), 401

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not myconfig.CONFIG.client_api_key:
            return abortjson()
        # 从请求头中获取 API key
        api_key = request.headers.get('X-API-Key')
        
        # 从查询参数中获取 API key（可选的备选方案）
        if not api_key:
            api_key = request.args.get('api_key')
        
        # 验证 API key
        if not api_key or api_key != myconfig.CONFIG.client_api_key:
            return abortjson()
        return f(*args, **kwargs)
    return decorated_function


def initDatabase():
    # 创建数据库表
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            logger.error(f'数据库初始化失败: str({e})')


@app.route('/api/mediadata')
@login_required
def apiMediaDbList():
    query = MediaRecord.query.outerjoin(TorrentRecord, TorrentRecord.media_id==MediaRecord.id)

    # search filter
    search = request.args.get('search[value]')
    if search:
        query = query.filter(db.or_(
            TorrentRecord.torname.like(f'%{search}%'),
            MediaRecord.tmdb_title.like(f'%{search}%'),
            MediaRecord.tmdb_id.like(f'%{search}%'),
            MediaRecord.imdb_id.like(f'%{search}%'),
            MediaRecord.torname_regex.like(f'%{search}%'),
        ))
    total_filtered = query.count()

    # sorting
    order = []
    i = 0
    while True:
        col_index = request.args.get(f'order[{i}][column]')
        if col_index is None:
            break
        col_name = request.args.get(f'columns[{col_index}][data]')
        if col_name not in ['torname_regex', 'tmdb_title', 'created_at']:
            col_name = 'created_at'
        descending = request.args.get(f'order[{i}][dir]') == 'desc'
        col = getattr(MediaRecord, col_name)
        if descending:
            col = col.desc()
        order.append(col)
        i += 1
    if order:
        query = query.order_by(*order)

    # pagination
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    query = query.offset(start).limit(length)

    # one-many datalist 
    datalist = []
    for mediaitem in query:
        data = mediaitem.to_dict()
        data['torname'] = 'abc'
        if mediaitem.torrents:
            data['torname'] = ','.join([z.torname+'|'+z.infolink for z in mediaitem.torrents])
        datalist.append(data)
    # response
    return {
        'data': datalist,
        'recordsFiltered': total_filtered,
        'recordsTotal': MediaRecord.query.count(),
        'draw': request.args.get('draw', type=int),
    }


# -------------------

def parseTMDbStr(tmdbstr):
    if tmdbstr.isnumeric():
        return '', tmdbstr
    m = re.search(r'(m(ovie)?|t(v)?)?[-_]?(\d+)', tmdbstr.strip(), flags=re.A | re.I)
    if m:
        if m[1]:
            catstr = 'movie' if m[1].startswith('m') else 'tv'
        else:
            catstr = ''
        return catstr, m[4]
    else:
        return '', ''
    
def foundTorNameInLocal(torinfo):
    record = TorrentRecord.query.filter(
        TorrentRecord.torname == torinfo.torname,
    ).first()
    return record.media if record else None


# 如果需要转义特殊字符的辅助函数
def escape_sql_string(value):
    """转义SQL字符串中的特殊字符"""
    if not value:
        return value
    # 转义单引号
    return value.replace("'", "''")


def foundTorNameRegexInLocal_Optimized(torinfo):
    """
    优化版本：结合了安全性和性能
    """
    try:
        if not torinfo.media_title:
            return None

        # 转义输入字符串以防SQL注入
        escaped_title = escape_sql_string(torinfo.media_title)
        
        if torinfo.tmdb_cat == 'movie':
            record = MediaRecord.query.filter(db.and_(
                MediaRecord.torname_regex.op('regexp')(escaped_title),
                MediaRecord.tmdb_cat == torinfo.tmdb_cat,
                MediaRecord.year == torinfo.year,
                MediaRecord.torname_regex.isnot(None),
                MediaRecord.torname_regex != ''
            )).first()
            if not record and torinfo.year:
                year = int(torinfo.year)
                record = MediaRecord.query.filter(db.and_(
                    MediaRecord.torname_regex.op('regexp')(escaped_title),
                    MediaRecord.tmdb_cat == torinfo.tmdb_cat,
                    MediaRecord.year.in_([str(year - 1), str(year + 1)]),
                    MediaRecord.torname_regex.isnot(None),
                    MediaRecord.torname_regex != ''
                )).first()
        else:
            record = MediaRecord.query.filter(db.and_(
                MediaRecord.torname_regex.op('regexp')(escaped_title),
                MediaRecord.tmdb_cat == torinfo.tmdb_cat,
                MediaRecord.torname_regex.isnot(None),
                MediaRecord.torname_regex != ''
            )).first()
            
        if not record:
            logger.info(f'No regex match found for title: {torinfo.media_title}')
            return None
            
        if not record.torname_regex:
            logger.error(f'empty torname_regex: {record.tmdb_title}, {record.tmdb_cat}-{record.tmdb_id}')
            return None

        return record
        
    except Exception as e:
        logger.error(f'Error in foundTorNameRegexInLocal_Optimized: {str(e)} for title "{torinfo.media_title}"')
        return None
    

def foundTorNameRegexInLocal(torinfo):
    try:
        if not torinfo.media_title:
            return None

        # Convert media_title to SQL LIKE pattern
        like_pattern = f"%{torinfo.media_title}%"
        # escaped_title = escape_regex_str(torinfo.media_title)
        
        if torinfo.tmdb_cat == 'movie':
            record = MediaRecord.query.filter(db.and_(
                MediaRecord.tmdb_title.like(like_pattern),
                # literal(escaped_title).op('regexp')(MediaRecord.torname_regex),
                MediaRecord.tmdb_cat == torinfo.tmdb_cat,
                MediaRecord.year == torinfo.year,
            )).first()
        else:
            record = MediaRecord.query.filter(db.and_(
                MediaRecord.tmdb_title.like(like_pattern),
                # literal(escaped_title).op('regexp')(MediaRecord.torname_regex),
                MediaRecord.tmdb_cat == torinfo.tmdb_cat
            )).first()
            
        if record and not record.torname_regex:
            logger.error(f'empty torname_regex: {record.tmdb_title}, {record.tmdb_cat}-{record.tmdb_id}')
            return None

        return record
        
    except Exception as e:
        logger.error(f'Error in foundTorNameRegexInLocal: {str(e)} for title "{torinfo.media_title}"')
        return None

def foundIMDbIdInLocal(imdb_id):
    record = MediaRecord.query.filter(db.and_(
        MediaRecord.imdb_id == imdb_id
    )).first()
    return record

def foundTMDbIdInLocal(tmdb_cat, tmdb_id):
    record = MediaRecord.query.filter(db.and_(
        MediaRecord.tmdb_cat == tmdb_cat,
        MediaRecord.tmdb_id == tmdb_id,
    )).first()
    return record

def recordJson(record):
    mediaJson = record.to_dict()
    mediaJson.pop('genre_str')
    return jsonify({
            'success': True,
            'data': mediaJson
        })

def recordNotfound():
    return jsonify({
        'success': False,
        'message': '未找到匹配记录'
    })


def saveTorrentRecord(mediarecord, torinfo):
    if not torinfo.infolink:
        return None

    # 检查是否已存在相同的 torname
    existing_torrent = TorrentRecord.query.filter_by(torname=torinfo.torname).first()
    if existing_torrent:
        logger.warning(f"TorrentRecord with torname '{torinfo.torname}' already exists. Skipping.")
        return existing_torrent  # 或者返回 None，取决于你希望如何处理重复记录

    trec = TorrentRecord(
        torname=torinfo.torname,
        infolink=torinfo.infolink,
        subtitle=torinfo.subtitle,
    )
    mediarecord.torrents.append(trec)
    db.session.add(trec)
    db.session.commit()
    return trec

def normalizeRegex(regexstr):
    if not isinstance(regexstr, str):
        raise ValueError("Input must be a string")

    if not regexstr.startswith('^'):
        regexstr = '^' + regexstr
    if not regexstr.endswith(r'$'):
        regexstr = regexstr + r'$'
    
    return regexstr

def escape_regex_str(s):
    """Escape special regex characters in string for MySQL regexp comparison"""
    special_chars = '[\\^$.|?*+(){}'
    return ''.join('\\' + c if c in special_chars else c for c in s)

def dupeTorNameRegex(torinfo):
    """
    检查当前torinfo.media_title作为torname_regex是否在数据库中已存在重复
    
    Args:
        torinfo: 包含media_title等属性的对象，media_title将作为新的torname_regex
        
    Returns:
        bool: True表示存在重复的torname_regex，False表示不重复
    """
    try:
        # 输入验证
        if not torinfo.media_title or not isinstance(torinfo.media_title, str):
            logger.warning(f'Invalid media_title: {getattr(torinfo, "torname", "Unknown")}')
            return False
                 
        if not torinfo.tmdb_cat or torinfo.tmdb_cat not in ['movie', 'tv']:
            logger.warning(f'Invalid tmdb_cat: {torinfo.tmdb_cat} for {getattr(torinfo, "torname", "Unknown")}')
            return False

        # 将要插入的torname_regex就是当前的media_title
        # new_regex_pattern = escape_sql_string(torinfo.media_title.strip())
        new_regex_pattern = torinfo.media_title.strip()
        
        # 检查数据库中是否已存在相同的torname_regex
        existing_record = MediaRecord.query.filter(
            MediaRecord.torname_regex == new_regex_pattern
        ).first()
        
        if existing_record:
            logger.warning(f"Found duplicate torname_regex: '{new_regex_pattern}' already exists in record "
                       f"ID={existing_record.id}, title='{existing_record.tmdb_title}', cat={existing_record.tmdb_cat}")
            return True
        else:
            logger.debug(f"No duplicate torname_regex: '{new_regex_pattern}'")
            return False
             
    except Exception as e:
        logger.error(f'Error in dupeTorNameRegex: {str(e)} for {getattr(torinfo, "torname", "Unknown")}')
        return False
    
# def dupeTorNameRegex(torinfo):
#     try:
#         if not torinfo.media_title or not isinstance(torinfo.media_title, str):
#             logger.warning(f'Invalid media_title: {torinfo.torname}')
#             return False
        
#         if not torinfo.tmdb_cat or torinfo.tmdb_cat not in ['movie', 'tv']:
#             logger.warning(f'Invalid tmdb_cat: {torinfo.tmdb_cat} for {torinfo.torname}')
#             return False

#         # Use simple LIKE pattern instead of regexp
#         like_pattern = f"%{torinfo.media_title}%"
        
#         record = MediaRecord.query.filter(db.and_(
#             MediaRecord.tmdb_title.like(like_pattern),
#             MediaRecord.tmdb_cat == torinfo.tmdb_cat,
#             MediaRecord.torname_regex.isnot(None)
#         )).first()
        
#         if record:
#             logger.info(f"Found duplicate title pattern: {torinfo.media_title} matches {record.tmdb_title}")
#         return record is not None
        
#     except Exception as e:
#         logger.error(f'Error in dupeTorNameRegex: {str(e)} for {torinfo.torname}')
#         return False


def saveMediaRecord(torinfo):
    if not torinfo.media_title:
        logger.error(f'empty media_title: {torinfo.torname}, {torinfo.tmdb_cat}-{torinfo.tmdb_id}')
        return None

    if dupeTorNameRegex(torinfo):
        logger.error(f'regex dupe: {torinfo.media_title} - {torinfo.torname}, {torinfo.tmdb_cat}-{torinfo.tmdb_id}')
        return None
    
    gidstr = ','.join(str(e) for e in torinfo.genre_ids)
    trec = TorrentRecord(
        torname=torinfo.torname,
        infolink=torinfo.infolink,
        subtitle=torinfo.subtitle,
    )
    mrec = MediaRecord(
            # 默认以 media_title 作为匹配
            torname_regex=normalizeRegex(torinfo.media_title),
            tmdb_title=torinfo.tmdb_title,
            tmdb_cat=torinfo.tmdb_cat,
            tmdb_id=torinfo.tmdb_id,
            imdb_id=torinfo.imdb_id,
            imdb_val=torinfo.imdb_val,
            year=torinfo.year,
            original_language=torinfo.original_language,
            popularity=torinfo.popularity,
            poster_path=torinfo.poster_path,
            release_air_date=torinfo.release_air_date,
            genre_ids=gidstr,
            origin_country=torinfo.origin_country,
            original_title=torinfo.original_title,
            overview=torinfo.overview,
            vote_average=torinfo.vote_average,
            production_countries=torinfo.production_countries,
        )
    mrec.torrents.append(trec)
    db.session.add(mrec)
    db.session.commit()
    logger.debug(f"Append new regex: {torinfo.media_title} {torinfo.year if torinfo.tmdb_cat == 'movie' else ''} - {torinfo.tmdb_cat}-{torinfo.tmdb_id}")
    return mrec

# 查询API接口
@app.route('/api/test_query', methods=['POST'])
def test_query():
    data = request.get_json()
    torname = data.get('torname')
    torinfo = TorrentParser.parse(torname)
    if not torinfo.media_title:
        logger.error(f'empty: torinfo.media_title ')
        recordNotfound()

    logger.info(f'查找本地 TorName Regex: {torinfo.media_title}')
    if mrec := foundTorNameRegexInLocal_Optimized(torinfo):
        trec = saveTorrentRecord(mrec, torinfo)
        logger.info(f'LOCAL REGEX: {torinfo.torname} ==> {mrec.tmdb_title}, {mrec.tmdb_cat}-{mrec.tmdb_id}')
        return recordJson(mrec)

    return {"message": "This is a test query"}

# 查询API接口
@app.route('/api/query', methods=['POST'])
@require_api_key
def query():
    # check_open_files()  # 添加检查
    data = request.get_json()
    torname = data.get('torname')
    if not torname:
        logger.error(f'no torname')
        recordNotfound()
    torinfo = TorrentParser.parse(torname)
    if not torinfo.media_title:
        logger.error(f'empty: torinfo.media_title ')
        recordNotfound()
    logger.info(f'>> torname: {torname}, media_title: {torinfo.media_title}, year: {torinfo.year}')

    if 'extitle' in data:
        torinfo.subtitle = data.get('extitle')
    if 'imdbid' in data:
        torinfo.imdb_id = data.get('imdbid')
    if 'tmdbstr' in data:
        torinfo.tmdb_cat, torinfo.tmdb_id = parseTMDbStr(data.get('tmdbstr'))
    if 'infolink' in data:
        torinfo.infolink = data.get('infolink')

    # 完全同名 种子
    if r1 := foundTorNameInLocal(torinfo):
        logger.info(f'LOCAL: {torinfo.torname} ==> {r1.tmdb_title}, {r1.tmdb_cat}-{r1.tmdb_id}')
        return recordJson(r1)

    if not myconfig.CONFIG.tmdb_api_key:
        logger.error('TMDb API Key 没有配置')
        return recordNotfound()
    ts = TMDbSearcher(myconfig.CONFIG.tmdb_api_key, myconfig.CONFIG.tmdb_lang)
    # 直接给了TMDb 
    if 'tmdbstr' in data:
        # 直接给了TMDb 先查本地
        logger.info(f'查找本地 TMDbId: {torinfo.tmdb_cat}-{torinfo.tmdb_id}')
        if mrec := foundTMDbIdInLocal(torinfo.tmdb_cat, torinfo.tmdb_id):
            trec = saveTorrentRecord(mrec, torinfo)
            logger.info(f'LOCAL TMDb: {torinfo.torname} ==> {mrec.tmdb_title}, {mrec.tmdb_cat}-{mrec.tmdb_id}')
            return recordJson(mrec)
        # 直接给了TMDb 本地没有，去 TMDb 查
        if r := ts.searchTMDbByTMDbId(torinfo):
            r2 = saveMediaRecord(torinfo)
            if r2:
                logger.info(f'TMDbId: {torinfo.torname} ==> {r2.tmdb_title}, {r2.tmdb_cat}-{r2.tmdb_id}')
                return recordJson(r2)
            else:
                return recordNotfound()
    # 有 IMDbId 且是电影
    if 'imdbid' in data and torinfo.tmdb_cat == 'movie':
        # 有IMDb 先查本地
        logger.info(f'电影，查找本地 IMDbId: {data.get("imdbid")}')
        if mrec := foundIMDbIdInLocal(data.get('imdbid')):
            trec = saveTorrentRecord(mrec, torinfo)
            logger.info(f'LOCAL IMDb: {torinfo.torname} ==> {mrec.tmdb_title}, {mrec.tmdb_cat}-{mrec.tmdb_id}')
            return recordJson(mrec)
        # 有IMDb 本地没有，去 TMDb 查
        if r := ts.searchTMDbByIMDbId(torinfo):
            r3 = saveMediaRecord(torinfo)
            if r3:
                logger.info(f'IMDbId: {torinfo.torname} ==> {r3.tmdb_title}, {r3.tmdb_cat}-{r3.tmdb_id}')
                return recordJson(r3)
            else:
                return recordNotfound()
            
    # TMDb 和 IMDb 都没给，先查本地 TorName Regex
    logger.info(f'查找本地 TorName Regex: {torinfo.media_title}')
    if mrec := foundTorNameRegexInLocal_Optimized(torinfo):
        trec = saveTorrentRecord(mrec, torinfo)
        logger.info(f'LOCAL REGEX: {torinfo.torname} ==> {mrec.tmdb_title}, {mrec.tmdb_cat}-{mrec.tmdb_id}')
        return recordJson(mrec)
    # TMDb 和 IMDb 都没给，本地 TorName Regex 没找到，去 Blind 搜
    logger.info(f'查找 TMDb, title: {torinfo.media_title}, Subtitle: {torinfo.subtitle}')
    if s := ts.searchTMDb(torinfo):
        if mrec := foundTMDbIdInLocal(torinfo.tmdb_cat, torinfo.tmdb_id):
            trec = saveTorrentRecord(mrec, torinfo)
            logger.info(f'LOCAL BLIND: {torinfo.torname} ==> {mrec.tmdb_title}, {mrec.tmdb_cat}-{mrec.tmdb_id}. confidence: {torinfo.confidence}')
            return recordJson(mrec)
        if torinfo.confidence < 30:
            logger.warning(f'BLIND confidence too low: {torinfo.confidence}, tor: {torinfo.torname} ==> {torinfo.tmdb_title}, {torinfo.tmdb_cat}-{torinfo.tmdb_id}')
            return recordJson()
        r4 = saveMediaRecord(torinfo)
        if r4:
            logger.info(f'BLIND: {torinfo.torname} ==> {r4.tmdb_title}, {r4.tmdb_cat}-{r4.tmdb_id}')
            return recordJson(r4)
        else:
            return recordNotfound()

    return recordNotfound()



# 新增 API接口
@app.route('/api/records', methods=['POST'])
def record_media():
    data = request.get_json()
    
    try:
        t = TorrentInfo()
        t.tmdb_cat=data['tmdb_cat']
        t.tmdb_id=data['tmdb_id']
        t.torname = '<自定义标题解析>'
        t.infolink = '/'
        t.subtitle = '<自定义标题解析>'
        t.media_title=data['torname_regex']
        t.tmdb_title=data['tmdb_title']
        t.year=data['year']
        mrec = saveMediaRecord(t)
        if t.tmdb_cat and t.tmdb_id:
            updateRecordTMDbInfo(mrec, t.tmdb_cat, t.tmdb_id)
            db.session.commit()
        t.tmdb_title=data['tmdb_title']
        return jsonify({
            'success': True,
            'data': mrec.to_dict()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400

# 获取所有记录
@app.route('/api/records', methods=['GET'])
def get_records():
    records = MediaRecord.query.all()
    return jsonify({
        'success': True,
        'data': [record.to_dict() for record in records]
    })

def clearMediaRecord(record):
    record.overview = ''
    record.production_countries = ''
    record.original_title = ''
    record.poster_path = ''
    record.original_language = ''
    record.genre_ids=''
    return record

def updateRecordTMDbInfo(record, tmdb_cat, tmdb_id):
    torinfo = TorrentInfo()
    torinfo.tmdb_cat = tmdb_cat
    torinfo.tmdb_id = tmdb_id
    ts = TMDbSearcher(myconfig.CONFIG.tmdb_api_key, myconfig.CONFIG.tmdb_lang)
    if r := ts.searchTMDbByTMDbId(torinfo):    
        record.tmdb_title = torinfo.tmdb_title
        record.tmdb_cat = torinfo.tmdb_cat
        record.tmdb_id = torinfo.tmdb_id
        record.imdb_id = torinfo.imdb_id
        record.imdb_val = torinfo.imdb_val
        record.year = torinfo.year
        record.original_language = torinfo.original_language
        record.popularity = torinfo.popularity
        record.poster_path = torinfo.poster_path
        record.release_air_date = torinfo.release_air_date
        gidstr = ','.join(str(e) for e in torinfo.genre_ids)
        record.genre_ids = gidstr
        record.origin_country = torinfo.origin_country
        record.original_title = torinfo.original_title
        record.overview = torinfo.overview
        record.vote_average = torinfo.vote_average
        record.production_countries = torinfo.production_countries
    return


# 修改 记录
@app.route('/api/records/<int:id>', methods=['PUT'])
def update_record(id):
    record = MediaRecord.query.get_or_404(id)
    data = request.get_json()
    
    try:
        tmdb_id = data.get('tmdb_id', '')
        tmdb_cat = data.get('tmdb_cat', '')
        record.torname_regex = data.get('torname_regex', record.torname_regex)
        record.tmdb_cat = data.get('tmdb_cat', record.tmdb_cat)
        record.tmdb_id = data.get('tmdb_id', record.tmdb_id)
        record.year = data.get('year', record.year)
        # if (tmdb_id != record.tmdb_id) or (tmdb_cat != record.tmdb_cat):
        if tmdb_id and tmdb_cat:
            updateRecordTMDbInfo(record, tmdb_cat, tmdb_id)
        else:
            clearMediaRecord(record)
        tmdb_title = data.get('tmdb_title', record.tmdb_title)
        if tmdb_title != record.tmdb_title:
            logger.warning(f'自定义标题： {tmdb_title} TMDb标题: {record.tmdb_title}')
            record.tmdb_title = tmdb_title
        db.session.commit()
        return jsonify({
            'success': True,
            'data': record.to_dict()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400

# 删除记录
@app.route('/api/records/<int:id>', methods=['DELETE'])
def delete_record(id):
    record = MediaRecord.query.get_or_404(id)
    
    try:
        db.session.delete(record)
        db.session.commit()
        return jsonify({
            'success': True,
            'message': '记录已删除'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400

# Web界面路由
@app.route('/')
@login_required
def index():
    return render_template('list.html')

LOG_FILE_NAME = "torcpdb.log"
def setupLogger():
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    log.disabled = True
    logger.remove()
    
    formatstr = "{time:YYYY-MM-DD HH:mm:ss} | <level>{level: <8}</level> | - <level>{message}</level>"
    logger.add(LOG_FILE_NAME, format=formatstr, rotation="500 MB") 
    logger.add(sys.stdout, format=formatstr)


def check_open_files():
    """检查打开的文件描述符数量"""
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    current = len(os.listdir('/proc/self/fd'))
    if current > (soft * 0.8):  # 如果超过软限制的80%
        logger.warning(f"Too many open files: {current}/{soft}")
        
def setup_file_limits():
    """提高文件描述符限制"""
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        resource.setrlimit(resource.RLIMIT_NOFILE, (max(4096, soft), hard))
        logger.info(f"File descriptor limits: {soft}/{hard}")
    except Exception as e:
        logger.error(f"Failed to set file limits: {e}")


def main():
    configfile = os.path.join(os.path.dirname(__file__), 'config.ini')
    myconfig.readConfig(configfile)
    loadMysqlConfig()
    setupLogger()
    setup_file_limits()  # 添加文件限制设置
    initDatabase()

    app.run(host='::', port=5009, debug=True)


if __name__ == '__main__':
    main()
