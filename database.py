from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(255), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    playlists = db.relationship('Playlist', backref='user', lazy=True, cascade='all, delete-orphan')

class Playlist(db.Model):
    __tablename__ = 'playlists'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    songs = db.relationship('Song', backref='playlist', lazy=True, cascade='all, delete-orphan')

class Song(db.Model):
    __tablename__ = 'songs'
    
    id = db.Column(db.Integer, primary_key=True)
    youtube_id = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(500), nullable=False)
    duration = db.Column(db.Integer)
    thumbnail = db.Column(db.String(1000))
    channel = db.Column(db.String(255))
    playlist_id = db.Column(db.Integer, db.ForeignKey('playlists.id'), nullable=False)
    position = db.Column(db.Integer, default=0)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Unique constraint to prevent duplicate songs in same playlist
    __table_args__ = (db.UniqueConstraint('youtube_id', 'playlist_id', name='unique_song_in_playlist'),)
