# app.py
from flask import Flask, request, jsonify, render_template, redirect, abort
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import literal
from sqlalchemy.orm import relationship
from datetime import datetime

import os, sys, re
from torinfo import TorrentParser, TorrentInfo
from tmdbsearcher import TMDbSearcher
import myconfig
from loguru import logger
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user


app = Flask(__name__)


# app.config['MYSQL_HOST'] = '127.0.0.1'
# app.config['MYSQL_USER'] = 'torll'
# app.config['MYSQL_PASSWORD'] = 'Cr#91237'
# app.config['MYSQL_DB'] = 'torcpdb'

# app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://{}:{}@{}/{}'.format(
#     app.config['MYSQL_USER'],
#     app.config['MYSQL_PASSWORD'],
#     app.config['MYSQL_HOST'],
#     app.config['MYSQL_DB']
# )

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///media.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

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


GENRE_IDS = {28: '动作', 12: '冒险', 16: '动画', 35: '喜剧', 80: '犯罪', 99: '纪录', 18: '剧情', 10751: '家庭',
             14: '奇幻', 36: '历史', 27: '恐怖', 10402: '音乐', 9648: '悬疑', 10749: '爱情', 878: '科幻', 10770: '电视电影',
             53: '惊悚', 10752: '战争', 37: '西部', 10759: '动作冒险', 10762: '儿童', 10763: '新闻', 10764: '真人秀', 
             10765: '科幻奇幻', 10766: '肥皂剧', 10767: '脱口秀', 10768: '战争政治'}


def tryint(instr):
    try:
        string_int = int(instr)
    except ValueError:    
        string_int = 0
    return string_int


def genreid2str(idstr):
    if not idstr:
        return ''
    idlist = [tryint(z) for z in idstr.split(',')]
    genre_names = ''
    if idlist:
        genre_names = [GENRE_IDS.get(id, '') for id in idlist if id in GENRE_IDS]
    
    # 返回结果，空格分隔
    return ' '.join(genre_names)


def truncate_string(input_string, max_length=128):
    if not input_string:
        return ''
    input_string = input_string.strip()
    # 如果字符串的长度大于最大长度，则截取并加上 '...'
    if len(input_string) > max_length:
        return input_string[:max_length] + '...'
    else:
        return input_string


# 数据模型
class TorrentRecord(db.Model):
    __tablename__ = "torrent_table"
    id = db.Column(db.Integer, primary_key=True)
    media_id = db.Column(db.Integer, db.ForeignKey('media_table.id'))
    media = db.relationship("MediaRecord", back_populates="torrents")

    torname = db.Column(db.String(200), nullable=False)
    infolink = db.Column(db.String(200), nullable=True)
    subtitle = db.Column(db.String(200), nullable=True)

class MediaRecord(db.Model):
    __tablename__ = "media_table"
    id = db.Column(db.Integer, primary_key=True)
    torrents = db.relationship('TorrentRecord', back_populates='media', cascade="all,delete")

    created_at = db.Column(db.DateTime, default=datetime.now)
    torname_regex = db.Column(db.String(200), nullable=False)
    tmdb_title = db.Column(db.String(200), nullable=False)
    tmdb_cat = db.Column(db.String(16))
    tmdb_id = db.Column(db.Integer)
    imdb_id = db.Column(db.String(16))
    imdb_val = db.Column(db.Float, default=0.0)
    year = db.Column(db.Integer)
    original_language = db.Column(db.String(16))
    popularity = db.Column(db.Float, default=0.0)
    poster_path = db.Column(db.String(128))
    release_air_date = db.Column(db.String(16))
    genre_ids = db.Column(db.String(200))
    origin_country = db.Column(db.String(10)) 
    original_title = db.Column(db.String(100)) 
    overview = db.Column(db.Text) 
    vote_average = db.Column(db.Float, default=0.0) 
    production_countries = db.Column(db.String(10)) 

    def to_dict(self):
        return {
            'id': self.id,
            'torname_regex': self.torname_regex,
            'tmdb_title': self.tmdb_title,
            'tmdb_cat': self.tmdb_cat,
            'tmdb_id': self.tmdb_id,
            'imdb_id': self.imdb_id,
            'imdb_val': self.imdb_val,
            'year': self.year,
            'original_language': self.original_language,
            'popularity': self.popularity,
            'poster_path': self.poster_path,
            'release_air_date': self.release_air_date,
            'genre_ids': self.genre_ids,
            'genre_str': genreid2str(self.genre_ids),
            'origin_country': self.origin_country,
            'original_title': self.original_title,
            'overview': truncate_string(self.overview),
            'vote_average': self.vote_average,
            'production_countries': self.production_countries,
            'created_at': self.created_at
        }

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


def foundTorNameRegexInLocal(torinfo):
    if not torinfo.media_title:
        return None
    if torinfo.tmdb_cat == 'movie':
        record = MediaRecord.query.filter(db.and_(
            literal(torinfo.media_title).op('regexp')(MediaRecord.torname_regex),
            MediaRecord.tmdb_cat == torinfo.tmdb_cat,
            MediaRecord.year == torinfo.year,
        )).first()
    else:
        record = MediaRecord.query.filter(db.and_(
            literal(torinfo.media_title).op('regexp')(MediaRecord.torname_regex),
            MediaRecord.tmdb_cat == torinfo.tmdb_cat
        )).first()
        
    if record and not record.torname_regex:
        logger.error(f'empty torname_regex: {record.tmdb_title}, {record.tmdb_cat}-{record.tmdb_id}')
        return None

    return record

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

def saveMediaRecord(torinfo):
    if not torinfo.media_title:
        logger.error(f'empty media_title: {torinfo.torname}, {torinfo.tmdb_cat}-{torinfo.tmdb_id}')
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
    return mrec


# 查询API接口
@app.route('/api/query', methods=['POST'])
@require_api_key
def query():
    data = request.get_json()
    torname = data.get('torname')
    if not torname:
        logger.error(f'no torname')
        recordNotfound()
    torinfo = TorrentParser.parse(torname)
    if not torinfo.media_title:
        logger.error(f'empty: torinfo.media_title ')
        recordNotfound()

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
    if 'imdbid' in data:
        # 有IMDb 先查本地
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
    if mrec := foundTorNameRegexInLocal(torinfo):
        trec = saveTorrentRecord(mrec, torinfo)
        logger.info(f'LOCAL REGEX: {torinfo.torname} ==> {mrec.tmdb_title}, {mrec.tmdb_cat}-{mrec.tmdb_id}')
        return recordJson(mrec)
    # TMDb 和 IMDb 都没给，本地 TorName Regex 没找到，去 Blind 搜
    if s := ts.searchTMDb(torinfo):
        if mrec := foundTMDbIdInLocal(torinfo.tmdb_cat, torinfo.tmdb_id):
            trec = saveTorrentRecord(mrec, torinfo)
            logger.info(f'LOCAL BLIND: {torinfo.torname} ==> {mrec.tmdb_title}, {mrec.tmdb_cat}-{mrec.tmdb_id}')
            return recordJson(mrec)
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


def main():
    configfile = os.path.join(os.path.dirname(__file__), 'config.ini')
    myconfig.readConfig(configfile)
    initDatabase()

    app.run(host='::', port=5009, debug=True)


if __name__ == '__main__':
    setupLogger()
    main()      
