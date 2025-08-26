from flask import Flask, request, jsonify, render_template, Response
import yt_dlp
import os
import json
import threading
import time

app = Flask(__name__)

# Ensure the download folder exists
os.makedirs("downloads", exist_ok=True)

# Global progress data
progress_data = {"status": "idle", "progress": "0%", "message": "Ready to download"}

def progress_hook(d):
    """Hook to update progress_data while downloading."""
    global progress_data
    if d['status'] == 'downloading':
        # Clean up the percentage
        percent_str = d.get('_percent_str', '0%').strip()
        percent_num = percent_str.replace('%', '')
        
        # Clean up the speed
        speed_str = d.get('_speed_str', '').strip()
        
        # Get file size info if available
        downloaded = d.get('downloaded_bytes', 0)
        total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
        
        progress_data["status"] = "downloading"
        progress_data["progress"] = percent_str
        
        # Create a user-friendly message
        if speed_str and total > 0:
            # Convert bytes to MB for readability
            downloaded_mb = downloaded / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            progress_data["message"] = f"Downloading... {percent_str} ({downloaded_mb:.1f}MB / {total_mb:.1f}MB) - {speed_str}"
        elif speed_str:
            progress_data["message"] = f"Downloading... {percent_str} - {speed_str}"
        else:
            progress_data["message"] = f"Downloading... {percent_str}"
            
    elif d['status'] == 'finished':
        progress_data["status"] = "finished"
        progress_data["progress"] = "100%"
        progress_data["message"] = "Download completed! Processing video..."

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/download", methods=["POST"])
def download_video():
    try:
        data = request.get_json()
        url = data.get("url")
        quality = data.get("quality")

        if not url:
            return jsonify({"error": "No URL provided"}), 400

        # If no quality is given, fallback to best available
        if not quality:
            quality = "best"

        # Reset progress data
        global progress_data
        progress_data = {"status": "starting", "progress": "0%", "message": "Initializing download..."}

        ydl_opts = {
            'format': f'bestvideo[height<={quality}]+bestaudio/best[height<={quality}]',
            'merge_output_format': 'mp4',
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'noplaylist': True,
            'progress_hooks': [progress_hook],
        }

        def run_download():
            global progress_data
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)
                    if not filename.endswith(".mp4"):
                        filename = os.path.splitext(filename)[0] + ".mp4"
                    progress_data["status"] = "finished"
                    progress_data["message"] = f"Downloaded: {info.get('title', 'Video')}"
                    progress_data["progress"] = "100%"
            except Exception as e:
                progress_data["status"] = "error"
                progress_data["message"] = f"Download failed: {str(e)}"
                progress_data["progress"] = "0%"

        # Run in a separate thread so Flask can still stream progress
        threading.Thread(target=run_download, daemon=True).start()

        return jsonify({"status": "started"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/progress")
def progress():
    """Server-Sent Events endpoint for progress updates."""
    def generate():
        global progress_data
        last_status = None
        
        while True:
            # Send current progress data
            yield f"data: {json.dumps(progress_data)}\n\n"
            
            # If download is finished or error occurred, send one more update and break
            if progress_data["status"] in ["finished", "error"]:
                if last_status != progress_data["status"]:
                    last_status = progress_data["status"]
                    time.sleep(1)  # Give a moment for final update
                    yield f"data: {json.dumps(progress_data)}\n\n"
                break
                
            last_status = progress_data["status"]
            time.sleep(0.5)  # Update every 500ms

    return Response(generate(), mimetype="text/event-stream", headers={
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no'  # Disable nginx buffering if present
    })

if __name__ == "__main__":
    app.run(debug=True, port=5000)