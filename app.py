# app.py
from flask import Flask, request, jsonify, render_template, redirect, abort
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

import os, sys
from torinfo import TorrentParser
from tmdbsearcher import TMDbSearcher
import myconfig
from loguru import logger
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///media.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

app.secret_key = 'torcpdb_secret_key'  # 用于签名 session
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
        user = User(auth.username)
        login_user(user)  # 登录用户
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
            login_user(user)  # 登录用户
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


# 数据模型
class MediaRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    seed_name = db.Column(db.String(200), nullable=False)
    media_name = db.Column(db.String(200), nullable=False)
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
    overview = db.Column(db.String(200)) 
    vote_average = db.Column(db.Float, default=0.0) 
    production_countries = db.Column(db.String(10)) 

    def to_dict(self):
        return {
            'id': self.id,
            'seed_name': self.seed_name,
            'media_name': self.media_name,
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
            'origin_country': self.origin_country,
            'original_title': self.original_title,
            'overview': self.overview,
            'vote_average': self.vote_average,
            'production_countries': self.production_countries,
            'created_at': self.created_at
        }

# 创建数据库表
with app.app_context():
    db.create_all()


@app.route('/api/mediadata')
@login_required
def apiMediaDbList():
    query = MediaRecord.query

    # search filter
    search = request.args.get('search[value]')
    if search:
        query = query.filter(db.or_(
            MediaRecord.seed_name.like(f'%{search}%'),
            MediaRecord.media_name.like(f'%{search}%'),
            MediaRecord.tmdb_id.like(f'%{search}%'),
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
        if col_name not in ['seed_name', 'media_name', 'created_at']:
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

    # response
    return {
        'data': [mediaitem.to_dict() for mediaitem in query],
        'recordsFiltered': total_filtered,
        'recordsTotal': MediaRecord.query.count(),
        'draw': request.args.get('draw', type=int),
    }


# -------------------

def foundNameInLocal(torinfo):
    record = MediaRecord.query.filter(db.or_(
        MediaRecord.media_name == torinfo.media_title,
        MediaRecord.seed_name == torinfo.torname,
    )).first()
    return record

def foundIMDbIdInLocal(imdb_id):
    record = MediaRecord.query.filter(db.or_(
        MediaRecord.imdb_id == imdb_id
    )).first()
    return record

def foundTMDbIdInLocal(tmdb_id, tmdb_cat):
    record = MediaRecord.query.filter(db.or_(
        MediaRecord.tmdb_cat == tmdb_cat,
        MediaRecord.tmdb_id == tmdb_id,
    )).first()
    return record

def recordJson(record):
    return jsonify({
            'success': True,
            'data': record.to_dict()
        })

def recordNotfound():
    return jsonify({
        'success': False,
        'message': '未找到匹配记录'
    })

def saveTorInfo(torinfo):
    gidstr = ','.join(str(e) for e in torinfo.genre_ids)
    mrec = MediaRecord(
            seed_name=torinfo.torname,
            media_name=torinfo.media_title,
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
    db.session.add(mrec)
    db.session.commit()
    return mrec


# 查询API接口
@app.route('/api/query', methods=['POST'])
@require_api_key
def query():
    data = request.get_json()
    torname = data.get('seed_name')
    torinfo = TorrentParser.parse(torname)
    if 'extitle' in data:
        torinfo.subtitle = data.get('extitle')
    if 'imdbid' in data:
        torinfo.imdb_id = data.get('imdbid')
    if 'tmdbid' in data:
        torinfo.tmdb_id = data.get('tmdbid')

    if r1 := foundNameInLocal(torinfo):
        logger.info(f'LOCAL: {r1.seed_name} ==> {r1.media_name}, {r1.tmdb_cat}-{r1.tmdb_id}')
        return recordJson(r1)

    if not myconfig.CONFIG.tmdb_api_key:
        logger.error('TMDb API Key 没有配置')
        return recordNotfound()
    ts = TMDbSearcher(myconfig.CONFIG.tmdb_api_key, myconfig.CONFIG.tmdb_lang)
    if 'tmdbid' in data:
        if r := ts.searchTMDbByTMDbId(torinfo, data.get('tmdbid')):
            r2 = saveTorInfo(torinfo)
            logger.info(f'TMDbId: {r2.seed_name} ==> {r2.media_name}, {r2.tmdb_cat}-{r2.tmdb_id}')
            return recordJson(r2)
    if 'imdbid' in data:
        if r1 := foundIMDbIdInLocal(data.get('imdbid')):
            logger.info(f'LOCAL IMDb: {r1.seed_name} ==> {r1.media_name}, {r1.tmdb_cat}-{r1.tmdb_id}')
            return recordJson(r1)
        if r := ts.searchTMDbByIMDbId(torinfo, data.get('imdbid')):
            r3 = saveTorInfo(torinfo)
            logger.info(f'IMDbId: {r3.seed_name} ==> {r3.media_name}, {r3.tmdb_cat}-{r3.tmdb_id}')
            return recordJson(r3)
    if s := ts.searchTMDb(torinfo):
        r4 = saveTorInfo(torinfo)
        logger.info(f'BLIND: {r4.seed_name} ==> {r4.media_name}, {r4.tmdb_cat}-{r4.tmdb_id}')
        return recordJson(r4)

    return recordNotfound()



# 查询API接口
@app.route('/api/query2', methods=['POST'])
def query_media():
    data = request.get_json()
    torname = data.get('seed_name')
    torinfo = TorrentParser.parse(torname)
    media_name = torinfo.media_name
    # 在数据库中查找匹配记录
    record = MediaRecord.query.filter(db.or_(
        MediaRecord.media_name.like(f'%{media_name}%'),
        MediaRecord.seed_name.like(f'%{media_name}%'),
    )).first()
    if record:
        return jsonify({
            'success': True,
            'data': record.to_dict()
        })
    
    # TODO: 这里可以添加外部API调用来获取正确的媒体信息
    # 示例返回
    return jsonify({
        'success': False,
        'message': '未找到匹配记录'
    })

# 记录API接口
@app.route('/api/record', methods=['POST'])
def record_media():
    data = request.get_json()
    
    try:
        new_record = MediaRecord(
            seed_name=data['seed_name'],
            media_name=data['media_name'],
            category=data['category'],
            tmdb_id=data['tmdb_id'],
            year=data['year']
        )
        
        db.session.add(new_record)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'data': new_record.to_dict()
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

# 更新记录
@app.route('/api/records/<int:id>', methods=['PUT'])
def update_record(id):
    record = MediaRecord.query.get_or_404(id)
    data = request.get_json()
    
    try:
        record.seed_name = data.get('seed_name', record.seed_name)
        record.media_name = data.get('media_name', record.media_name)
        record.category = data.get('category', record.category)
        record.tmdb_id = data.get('tmdb_id', record.tmdb_id)
        record.year = data.get('year', record.year)
        
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

def setupLogger():
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    log.disabled = True
    logger.remove()
    
    formatstr = "{time:YYYY-MM-DD HH:mm:ss} | <level>{level: <8}</level> | - <level>{message}</level>"
    logger.add(sys.stdout, format=formatstr)


def main():
    configfile = os.path.join(os.path.dirname(__file__), 'config.ini')
    myconfig.readConfig(configfile)

    app.run(host='0.0.0.0', port=5009, debug=True)


if __name__ == '__main__':
    setupLogger()
    main()      
