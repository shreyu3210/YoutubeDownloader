from flask import Flask, render_template, request, jsonify, Response
import yt_dlp
import threading
import os

app = Flask(__name__)
progress_data = {"status": "idle", "progress": "0%", "message": ""}

# Make sure downloads folder exists
if not os.path.exists("downloads"):
    os.makedirs("downloads")


def download_video(url, quality):
    global progress_data
    progress_data = {"status": "downloading", "progress": "0%", "message": ""}

    def hook(d):
        if d['status'] == 'downloading':
            progress_data["progress"] = d.get('_percent_str', '0%')
            progress_data["message"] = f"Downloading: {d['_percent_str']} at {d.get('_speed_str', '')}"
        elif d['status'] == 'finished':
            progress_data["status"] = "finished"
            progress_data["message"] = "Download complete!"

    ydl_opts = {
        'format': f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]',
        'progress_hooks': [hook],
        'outtmpl': 'downloads/%(title)s.%(ext)s'
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/download", methods=["POST"])
def download():
    url = request.form.get("url")
    quality = request.form.get("quality")

    # Run in background thread
    threading.Thread(target=download_video, args=(url, quality)).start()

    return jsonify({"status": "started"})


@app.route("/progress")
def progress():
    def generate():
        while progress_data["status"] != "finished":
            yield f"data: {progress_data}\n\n"
        yield f"data: {progress_data}\n\n"

    return Response(generate(), mimetype="text/event-stream")


if __name__ == "__main__":
    app.run(debug=True)
