from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from datetime import datetime
from utils import genreid2str, truncate_string



db = SQLAlchemy()


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