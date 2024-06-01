import yt_dlp as youtube_dl
import os

def download_song(song_title):
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'flac',
            'preferredquality': 'lossless',
        }],
        'outtmpl': '%(uploader)s_%(upload_date>%Y-%m-%d)s_%(title)s.%(ext)s}}' ,  # Output filename template
        'restrictfilenames': True,  # Restrict filenames to ASCII characters
    }

    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        ydl.download([f"ytsearch1:{song_title}"])

def download_songs_from_file(file_path):
    if not os.path.isfile(file_path):
        print(f"File {file_path} does not exist.")
        return

    with open(file_path, 'r') as file:
        songs = file.readlines()

    for song in songs:
        song = song.strip()
        if song:
            print(f"Downloading: {song}")
            download_song(song)

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python music-ld.py <file_path>")
        sys.exit(1)
    file_path = sys.argv[1]
    download_songs_from_file(file_path)
