import os
import re
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# Load environment variables
load_dotenv()

CLIENT_ID = "4b518e8e895841258e8a4b7599935ba1"
CLIENT_SECRET = "2dea1282cb9c4ef9b0364c825fe623e7"
OUTPUT_FILE_NAME = "songs.txt"

# Initialize Spotify API client
client_credentials_manager = SpotifyClientCredentials(client_id=CLIENT_ID, client_secret=CLIENT_SECRET)
sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

# Function to get playlist URI from link
def get_playlist_uri(playlist_link):
    match = re.match(r"https://open.spotify.com/playlist/(.*)\?", playlist_link)
    if match:
        return match.groups()[0]
    else:
        raise ValueError("Invalid Spotify playlist link")

# Function to extract all track names and artists from a playlist
def get_all_tracks_info(playlist_uri):
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

# Main function
def main():
    playlist_link = input("Enter Spotify playlist link: ")
    playlist_uri = get_playlist_uri(playlist_link)
    tracks_info = get_all_tracks_info(playlist_uri)
    
    with open(OUTPUT_FILE_NAME, "w", encoding="utf-8") as file:
        for info in tracks_info:
            file.write(f"{info}\n")
    
    print(f"Track names have been saved to {OUTPUT_FILE_NAME}")

if __name__ == "__main__":
    main()
