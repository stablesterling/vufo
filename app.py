from flask import Flask, render_template, request, jsonify, session, make_response
from flask_cors import CORS
import yt_dlp
import json
import os
import re
import uuid
from datetime import datetime
from database import db, User, Playlist, Song

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

# Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'postgresql://vofodb_user:Y7MQfAWwEtsiHQLiGHFV7ikOI2ruTv3u@dpg-d5lm4ongi27c7390kq40-a/vofodb')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize extensions
db.init_app(app)
CORS(app)

# Configure yt-dlp options
ydl_opts = {
    'format': 'bestaudio/best',
    'quiet': True,
    'no_warnings': True,
    'extract_flat': True,
    'force_generic_extractor': False,
}

def get_or_create_user():
    """Get or create a user based on session ID"""
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    
    user = User.query.filter_by(session_id=session['user_id']).first()
    if not user:
        user = User(session_id=session['user_id'])
        db.session.add(user)
        db.session.commit()
    
    return user

def get_video_info(url):
    """Extract video information using yt-dlp"""
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'id': info.get('id'),
                'title': info.get('title'),
                'duration': info.get('duration'),
                'thumbnail': info.get('thumbnail'),
                'channel': info.get('channel'),
                'url': f"https://www.youtube.com/watch?v={info.get('id')}"
            }
    except Exception as e:
        print(f"Error fetching video info: {e}")
        return None

def search_youtube(query, limit=10):
    """Search YouTube for videos"""
    try:
        ydl_opts_search = ydl_opts.copy()
        ydl_opts_search['extract_flat'] = 'in_playlist'
        
        with yt_dlp.YoutubeDL(ydl_opts_search) as ydl:
            results = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
            
            videos = []
            if 'entries' in results:
                for entry in results['entries']:
                    if entry:
                        videos.append({
                            'id': entry.get('id'),
                            'title': entry.get('title'),
                            'duration': entry.get('duration'),
                            'thumbnail': entry.get('thumbnail'),
                            'channel': entry.get('channel'),
                            'url': f"https://www.youtube.com/watch?v={entry.get('id')}"
                        })
            return videos
    except Exception as e:
        print(f"Error searching: {e}")
        return []

def extract_video_id(url):
    """Extract YouTube video ID from various URL formats"""
    patterns = [
        r'(?:youtube\.com\/watch\?v=)([\w-]{11})',
        r'(?:youtu\.be\/)([\w-]{11})',
        r'(?:youtube\.com\/embed\/)([\w-]{11})',
        r'(?:youtube\.com\/v\/)([\w-]{11})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    if len(url) == 11 and re.match(r'^[\w-]+$', url):
        return url
    
    return None

@app.route('/')
def index():
    """Serve the main application page"""
    return render_template('index.html')

@app.route('/api/search', methods=['GET'])
def search():
    """Search for YouTube videos"""
    query = request.args.get('q', '')
    if not query:
        return jsonify({'error': 'No query provided'}), 400
    
    results = search_youtube(query)
    return jsonify({'results': results})

@app.route('/api/get_stream_url', methods=['GET'])
def get_stream_url():
    """Get streaming URL for a YouTube video"""
    video_id = request.args.get('video_id')
    url = request.args.get('url')
    
    if not video_id and not url:
        return jsonify({'error': 'No video ID or URL provided'}), 400
    
    if not video_id and url:
        video_id = extract_video_id(url)
    
    if not video_id:
        return jsonify({'error': 'Could not extract video ID'}), 400
    
    try:
        ydl_opts_stream = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts_stream) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            
            formats = info.get('formats', [])
            audio_formats = [f for f in formats if f.get('acodec') != 'none' and f.get('vcodec') == 'none']
            
            if audio_formats:
                best_format = max(audio_formats, key=lambda x: x.get('abr', 0) or 0)
                stream_url = best_format.get('url')
            else:
                for fmt in formats:
                    if fmt.get('acodec') != 'none':
                        stream_url = fmt.get('url')
                        break
                else:
                    stream_url = formats[0].get('url') if formats else None
            
            if stream_url:
                return jsonify({
                    'stream_url': stream_url,
                    'title': info.get('title'),
                    'duration': info.get('duration'),
                    'thumbnail': info.get('thumbnail')
                })
            else:
                return jsonify({'error': 'Could not extract stream URL'}), 500
                
    except Exception as e:
        print(f"Error getting stream URL: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/playlist/create', methods=['POST'])
def create_playlist():
    """Create a new playlist"""
    data = request.json
    playlist_name = data.get('name')
    
    if not playlist_name:
        return jsonify({'error': 'Playlist name is required'}), 400
    
    user = get_or_create_user()
    
    # Check if playlist already exists for this user
    existing = Playlist.query.filter_by(user_id=user.id, name=playlist_name).first()
    if existing:
        return jsonify({'error': 'Playlist already exists'}), 400
    
    playlist = Playlist(name=playlist_name, user_id=user.id)
    db.session.add(playlist)
    db.session.commit()
    
    return jsonify({'success': True, 'playlist': {'id': playlist.id, 'name': playlist.name}})

@app.route('/api/playlist/add', methods=['POST'])
def add_to_playlist():
    """Add a song to a playlist"""
    data = request.json
    playlist_id = data.get('playlist_id')
    song_data = data.get('song')
    
    if not playlist_id or not song_data:
        return jsonify({'error': 'Missing parameters'}), 400
    
    user = get_or_create_user()
    playlist = Playlist.query.filter_by(id=playlist_id, user_id=user.id).first()
    
    if not playlist:
        return jsonify({'error': 'Playlist not found'}), 404
    
    # Check if song already exists in playlist
    existing = Song.query.filter_by(youtube_id=song_data['id'], playlist_id=playlist_id).first()
    if existing:
        return jsonify({'success': True, 'message': 'Song already in playlist'})
    
    # Get next position
    last_song = Song.query.filter_by(playlist_id=playlist_id).order_by(Song.position.desc()).first()
    next_position = last_song.position + 1 if last_song else 0
    
    song = Song(
        youtube_id=song_data['id'],
        title=song_data['title'],
        duration=song_data.get('duration'),
        thumbnail=song_data.get('thumbnail'),
        channel=song_data.get('channel'),
        playlist_id=playlist_id,
        position=next_position
    )
    
    db.session.add(song)
    db.session.commit()
    
    return jsonify({'success': True, 'song': {
        'id': song.youtube_id,
        'title': song.title,
        'duration': song.duration,
        'thumbnail': song.thumbnail,
        'channel': song.channel
    }})

@app.route('/api/playlist/remove', methods=['POST'])
def remove_from_playlist():
    """Remove a song from a playlist"""
    data = request.json
    playlist_id = data.get('playlist_id')
    song_id = data.get('song_id')
    
    if not playlist_id or not song_id:
        return jsonify({'error': 'Missing parameters'}), 400
    
    user = get_or_create_user()
    playlist = Playlist.query.filter_by(id=playlist_id, user_id=user.id).first()
    
    if not playlist:
        return jsonify({'error': 'Playlist not found'}), 404
    
    song = Song.query.filter_by(youtube_id=song_id, playlist_id=playlist_id).first()
    if song:
        db.session.delete(song)
        db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/playlist/delete', methods=['POST'])
def delete_playlist():
    """Delete a playlist"""
    data = request.json
    playlist_id = data.get('playlist_id')
    
    if not playlist_id:
        return jsonify({'error': 'Playlist ID is required'}), 400
    
    user = get_or_create_user()
    playlist = Playlist.query.filter_by(id=playlist_id, user_id=user.id).first()
    
    if not playlist:
        return jsonify({'error': 'Playlist not found'}), 404
    
    db.session.delete(playlist)
    db.session.commit()
    
    return jsonify({'success': True})

@app.route('/api/playlist/<int:playlist_id>', methods=['GET'])
def get_playlist(playlist_id):
    """Get songs in a playlist"""
    user = get_or_create_user()
    playlist = Playlist.query.filter_by(id=playlist_id, user_id=user.id).first()
    
    if not playlist:
        return jsonify({'error': 'Playlist not found'}), 404
    
    songs = Song.query.filter_by(playlist_id=playlist_id).order_by(Song.position).all()
    songs_data = [{
        'id': song.youtube_id,
        'title': song.title,
        'duration': song.duration,
        'thumbnail': song.thumbnail,
        'channel': song.channel
    } for song in songs]
    
    return jsonify({'playlist': {'id': playlist.id, 'name': playlist.name}, 'songs': songs_data})

@app.route('/api/playlists', methods=['GET'])
def get_all_playlists():
    """Get all playlists for the current user"""
    user = get_or_create_user()
    playlists = Playlist.query.filter_by(user_id=user.id).all()
    
    playlists_data = []
    for playlist in playlists:
        song_count = Song.query.filter_by(playlist_id=playlist.id).count()
        playlists_data.append({
            'id': playlist.id,
            'name': playlist.name,
            'song_count': song_count,
            'created_at': playlist.created_at.isoformat() if playlist.created_at else None
        })
    
    return jsonify({'playlists': playlists_data})

@app.route('/api/current_playlist', methods=['GET', 'POST', 'DELETE'])
def current_playlist():
    """Manage current playing playlist (temporary session storage)"""
    if 'current_playlist' not in session:
        session['current_playlist'] = []
    
    if request.method == 'GET':
        return jsonify({'songs': session['current_playlist']})
    
    elif request.method == 'POST':
        data = request.json
        action = data.get('action')
        
        if action == 'add':
            song = data.get('song')
            if song and song['id'] not in [s['id'] for s in session['current_playlist']]:
                session['current_playlist'].append(song)
                session.modified = True
                return jsonify({'success': True, 'songs': session['current_playlist']})
        
        elif action == 'clear':
            session['current_playlist'] = []
            session.modified = True
            return jsonify({'success': True, 'songs': []})
        
        elif action == 'set':
            songs = data.get('songs', [])
            session['current_playlist'] = songs
            session.modified = True
            return jsonify({'success': True, 'songs': songs})
    
    elif request.method == 'DELETE':
        song_id = request.args.get('song_id')
        if song_id:
            session['current_playlist'] = [song for song in session['current_playlist'] if song['id'] != song_id]
            session.modified = True
            return jsonify({'success': True, 'songs': session['current_playlist']})
    
    return jsonify({'error': 'Invalid action'}), 400

@app.route('/service-worker.js')
def service_worker():
    """Serve the service worker for PWA functionality"""
    response = make_response(render_template('service-worker.js'))
    response.headers['Content-Type'] = 'application/javascript'
    response.headers['Service-Worker-Allowed'] = '/'
    return response

@app.route('/manifest.json')
def manifest():
    """Web App Manifest for PWA"""
    manifest_data = {
        "name": "MusicStream",
        "short_name": "MusicStream",
        "description": "YouTube Music Streaming App",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#1e1e2e",
        "theme_color": "#ff4757",
        "icons": [
            {
                "src": "https://cdn-icons-png.flaticon.com/512/727/727241.png",
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": "https://cdn-icons-png.flaticon.com/512/727/727241.png",
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    }
    return jsonify(manifest_data)

# Create database tables
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
