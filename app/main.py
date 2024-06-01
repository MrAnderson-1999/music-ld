from flask import Blueprint, request, render_template, jsonify
from .tasks import download_and_upload_playlist, task_status

main = Blueprint('main', __name__)

@main.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        playlist_link = request.form['playlist_link']
        try:
            task = download_and_upload_playlist.delay(playlist_link)
            return jsonify({'status': 'Task started!', 'task_id': task.id}), 202
        except Exception as e:
            return jsonify({'status': 'Error', 'message': str(e)}), 500
    return render_template('index.html')

@main.route('/status/<task_id>', methods=['GET'])
def taskstatus(task_id):
    response = task_status(task_id)
    return jsonify(response)
