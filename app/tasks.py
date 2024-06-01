from app import celery
from utils import clear_download_folder, get_playlist_uri, get_all_tracks_info, download_songs_from_file, zip_folder, create_presigned_url, logger, s3_client
from boto3.s3.transfer import TransferConfig
from celery import current_task
import os

@celery.task(bind=True)
def download_and_upload_playlist(self, playlist_link):
    try:
        DOWNLOAD_FOLDER = "downloads"
        S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "music-ld-downloads")
        OUTPUT_FILE_NAME = "songs.txt"

        clear_download_folder(DOWNLOAD_FOLDER)

        playlist_uri = get_playlist_uri(playlist_link)
        tracks_info = get_all_tracks_info(playlist_uri)

        with open(OUTPUT_FILE_NAME, "w", encoding="utf-8") as file:
            for info in tracks_info:
                file.write(f"{info}\n")

        current_task.update_state(state='PROGRESS', meta={'status': 'Downloading songs...'})
        download_songs_from_file(OUTPUT_FILE_NAME, DOWNLOAD_FOLDER)

        if os.listdir(DOWNLOAD_FOLDER):
            zip_path = os.path.join(DOWNLOAD_FOLDER, "downloads.zip")
            zip_folder(DOWNLOAD_FOLDER, zip_path)

            current_task.update_state(state='PROGRESS', meta={'status': 'Uploading to S3...'})

            # Configuring multipart upload
            GB = 1024 ** 3
            config = TransferConfig(multipart_threshold=5*GB, max_concurrency=10, use_threads=True)

            s3_client.upload_file(zip_path, S3_BUCKET_NAME, "downloads.zip", Config=config)

            current_task.update_state(state='PROGRESS', meta={'status': 'Files have been uploaded, preparing the link now...'})

            presigned_url = create_presigned_url(S3_BUCKET_NAME, "downloads.zip")

            current_task.update_state(state='PROGRESS', meta={'status': 'Link is retrieved', 'result': presigned_url})

            return {'status': 'Task completed!', 'result': presigned_url}
        else:
            return {'status': 'No files downloaded.'}
    except Exception as e:
        current_task.update_state(state='FAILURE', meta={'status': f'Error: {str(e)}'})
        return {'status': 'Task failed.', 'message': str(e)}

def task_status(task_id):
    task = download_and_upload_playlist.AsyncResult(task_id)
    if task.state == 'PENDING':
        response = {'state': task.state, 'status': 'Pending...'}
    elif task.state == 'PROGRESS':
        response = {'state': task.state, 'status': task.info.get('status', ''), 'result': task.info.get('result', '')}
    elif task.state == 'SUCCESS':
        response = {'state': task.state, 'status': 'Task completed!', 'result': task.info.get('result', '')}
    else:
        response = {'state': task.state, 'status': str(task.info)}
    return response
