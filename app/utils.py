import os
import re
import yt_dlp as youtube_dl
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import logging
from logging.handlers import RotatingFileHandler
import boto3
import zipfile
from botocore.exceptions import NoCredentialsError

# Load environment variables
load_dotenv()

CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "4b518e8e895841258e8a4b7599935ba1")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "2dea1282cb9c4ef9b0364c825fe623e7")

# Initialize Spotify API client
client_credentials_manager = SpotifyClientCredentials(client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

# Initialize S3 client
s3_client = boto3.client(
    's3',
    region_name=os.getenv("AWS_REGION"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)

# Configure logging to file with rotation
log_formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
log_file = 'mld.log'
log_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=2)
log_handler.setFormatter(log_formatter)
log_handler.setLevel(logging.DEBUG)

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
            break;
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

def zip_folder(folder_path, zip_path):
    logger.info(f"Zipping folder: {folder_path}")
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as zipf:
            for root, dirs, files in os.walk(folder_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    if file_path != zip_path:
                        arcname = os.path.relpath(file_path, folder_path)
                        logger.debug(f"Adding {file_path} as {arcname}")
                        zipf.write(file_path, arcname)
        logger.info("Folder zipped successfully.")
    except Exception as e:
        logger.error(f"Error zipping folder: {str(e)}")
        raise

def create_presigned_url(bucket_name, object_name, expiration=1800):
    try:
        response = s3_client.generate_presigned_url('get_object',
                                                    Params={'Bucket': bucket_name, 'Key': object_name},
                                                    ExpiresIn=expiration)
    except Exception as e:
        logger.error(f"Error generating presigned URL: {str(e)}")
        return None

    return response
