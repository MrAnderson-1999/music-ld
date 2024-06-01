from flask import Flask, Blueprint, request, render_template, jsonify
from celery import Celery, current_task
import os
import re
import yt_dlp as youtube_dl
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import logging
from logging.handlers import RotatingFileHandler
import boto3
from boto3.s3.transfer import TransferConfig
from botocore.exceptions import NoCredentialsError

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'default_secret_key')

app.config.update(
    CELERY_BROKER_URL='redis://localhost:6379/0',
    CELERY_RESULT_BACKEND='redis://localhost:6379/0'
)

# Initialize Celery
def make_celery(app):
    celery = Celery(
        app.import_name,
        backend=app.config['CELERY_RESULT_BACKEND'],
        broker=app.config['CELERY_BROKER_URL']
    )
    celery.conf.update(app.config)
    return celery

celery = make_celery(app)

# Initialize Spotify API client
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "4b518e8e895841258e8a4b7599935ba1")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "2dea1282cb9c4ef9b0364c825fe623e7")

client_credentials_manager = SpotifyClientCredentials(client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

# Initialize S3 client
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "music-ld-downloads")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION = os.getenv("AWS_REGION")

s3_client = boto3.client(
    's3',
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY
)

# Configure logging to file with rotation
log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
log_file = 'mld.log'
log_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=2)
log_handler.setFormatter(log_formatter)
log_handler.setLevel(logging.DEBUG)

app.logger.addHandler(log_handler)
app.logger.setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)
logger.addHandler(log_handler)
logger.setLevel(logging.DEBUG)

DOWNLOAD_FOLDER = "downloads"
OUTPUT_FILE_NAME = "songs.txt"

if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

def clear_download_folder(folder_path):
    logger.info(f"Clearing folder: {folder_path}")
    for root, dirs, files in os.walk(folder_path, topdown=False):
        for name in files:
            os.remove(os.path.join(root, name))
        for name in dirs:
            os.rmdir(os.path.join(root, name))

def get_playlist_uri(playlist_link):
    logger.debug("Extracting playlist URI from link.")
    match = re.match(r"https://open.spotify.com/playlist/(.*)\?", playlist_link)
    if match:
        return match.groups()[0]
    else:
        raise ValueError("Invalid Spotify playlist link")

def get_playlist_name(playlist_uri):
    playlist = sp.playlist(playlist_uri, fields="name")
    return playlist['name']

def get_all_tracks_info(playlist_uri):
    logger.debug("Fetching all track information from Spotify playlist.")
    tracks_info = []
    offset = 0
    while True:
        response = sp.playlist_tracks(playlist_uri, offset=offset, fields="items.track.name,items.track.artists.name,total,next")
        tracks = response["items"]
        for track in tracks:
            track_name = track["track"]["name"]
            artist_names = ", ".join([artist["name"] for artist in track["track"]["artists"]])
            tracks_info.append(f"{artist_names} - {track_name}")
        if response["next"] is None:
            break
        offset += len(tracks)
    return tracks_info

def download_song(song_title, download_folder):
    logger.info(f"Downloading song: {song_title}")
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'flac',
            'preferredquality': 'lossless',
        }],
        'outtmpl': os.path.join(download_folder, '%(title)s.%(ext)s'),
        'restrictfilenames': True,
        'nocheckcertificate': True,
        'ignoreerrors': True,
        'noplaylist': True,
        'quiet': False,
        'nooverwrites': True,
        'postprocessor_args': ['-vn'],
        'write_all_thumbnails': False,
        'writesubtitles': False,
        'socket_timeout': 30,
        'logger': logger,
    }

    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        try:
            ydl.download([f"ytsearch1:{song_title}"])
            logger.info(f"Successfully downloaded: {song_title}")
        except Exception as e:
            logger.error(f"Error downloading {song_title}: {str(e)}")

def download_songs_from_file(file_path, download_folder):
    if not os.path.isfile(file_path):
        logger.error(f"File {file_path} does not exist.")
        return

    with open(file_path, 'r') as file:
        songs = file.readlines()

    for song in songs:
        song = song.strip()
        if song:
            logger.debug(f"Downloading: {song}")
            download_song(song, download_folder)

def create_presigned_url(bucket_name, object_name, expiration=3600):
    try:
        response = s3_client.generate_presigned_url('get_object',
                                                    Params={'Bucket': bucket_name, 'Key': object_name},
                                                    ExpiresIn=expiration)
    except Exception as e:
        logger.error(f"Error generating presigned URL: {str(e)}")
        return None

    return response

def upload_folder_to_s3(folder_path, bucket_name, object_name_prefix):
    for root, dirs, files in os.walk(folder_path):
        for filename in files:
            file_path = os.path.join(root, filename)
            relative_path = os.path.relpath(file_path, folder_path)
            s3_path = os.path.join(object_name_prefix, relative_path)
            try:
                s3_client.upload_file(file_path, bucket_name, s3_path)
                logger.info(f"File uploaded to S3: {s3_path}")
            except NoCredentialsError:
                logger.error("Credentials not available for S3 upload.")
                return False
            except Exception as e:
                logger.error(f"Error uploading {file_path} to S3: {str(e)}")
                return False
    return True

@celery.task(bind=True)
def download_and_upload_playlist(self, playlist_link):
    try:
        clear_download_folder(DOWNLOAD_FOLDER)

        self.update_state(state='PROGRESS', meta={'status': 'Extracting playlist URI...'})
        playlist_uri = get_playlist_uri(playlist_link)
        playlist_name = get_playlist_name(playlist_uri).replace(" ", "_")  # Replacing spaces with underscores
        tracks_info = get_all_tracks_info(playlist_uri)
        total_songs = len(tracks_info)

        self.update_state(state='PROGRESS', meta={'status': 'Saving tracks information...', 'downloaded': 0, 'total': total_songs})
        with open(OUTPUT_FILE_NAME, "w", encoding="utf-8") as file:
            for info in tracks_info:
                file.write(f"{info}\n")

        downloaded_songs = 0
        for song in tracks_info:
            download_song(song, DOWNLOAD_FOLDER)
            downloaded_songs += 1
            self.update_state(state='PROGRESS', meta={'status': f'Downloading songs... ({downloaded_songs}/{total_songs})', 'downloaded': downloaded_songs, 'total': total_songs})

        if os.listdir(DOWNLOAD_FOLDER):
            self.update_state(state='PROGRESS', meta={'status': 'Uploading to S3...', 'downloaded': total_songs, 'total': total_songs})

            if upload_folder_to_s3(DOWNLOAD_FOLDER, S3_BUCKET_NAME, playlist_name):
                self.update_state(state='PROGRESS', meta={'status': 'Files have been uploaded, preparing the link now...', 'downloaded': total_songs, 'total': total_songs})

                presigned_url = create_presigned_url(S3_BUCKET_NAME, playlist_name)

                self.update_state(state='PROGRESS', meta={'status': 'Link is retrieved', 'result': presigned_url})
                
                clear_download_folder(DOWNLOAD_FOLDER)
                return {'status': 'Task completed!', 'result': presigned_url}
            else:
                return {'status': 'Upload to S3 failed.'}
        else:
            return {'status': 'No files downloaded.'}
    except Exception as e:
        self.update_state(state='FAILURE', meta={'status': f'Error: {str(e)}'})
        return {'status': 'Task failed.', 'message': str(e)}

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        playlist_link = request.form['playlist_link']
        task = download_and_upload_playlist.delay(playlist_link)
        return jsonify({'status': 'Task started!', 'task_id': task.id})
    return render_template('index.html')

@app.route('/status/<task_id>')
def taskstatus(task_id):
    task = download_and_upload_playlist.AsyncResult(task_id)
    if task.state == 'PENDING':
        response = {
            'state': task.state,
            'status': 'Pending...'
        }
    elif task.state != 'FAILURE':
        response = {
            'state': task.state,
            'status': task.info.get('status', ''),
            'downloaded': task.info.get('downloaded', 0),
            'total': task.info.get('total', 1)
        }
        if 'result' in task.info:
            response['result'] = task.info['result']
    else:
        response = {
            'state': task.state,
            'status': str(task.info),
        }
    return jsonify(response)

if __name__ == '__main__':
    app.run(debug=True)
