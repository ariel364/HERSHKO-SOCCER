import socket
import tqdm
import os
import cv2
import struct
from main import read_video_file, Tracker, CameraMovmentEstimator, ViewTransformer, SpeedAndDistance_Estimator, PlayerBallAssigner, PassCounter, save_video
from PassCounter import PassCounter
from utils import save_video, read_video  # פונקציות לקריאת ושמירת וידאו
from trackers import Tracker  # מעקב אחרי אובייקטים בסרטון
from team_assigner import TeamAssigner  # קביעת הקבוצות של השחקנים
from player_ball_assigner import PlayerBallAssigner  # קביעת השחקן שמחזיק בכדור
from camera_movment_estimator import CameraMovmentEstimator  # הערכת תנועת המצלמה
from view_transformer import ViewTransformer  # שינוי מיקום נקודות בסרטון
from speed_and_distance_estimator import SpeedAndDistance_Estimator  # הערכת מהירות ומרחק של השחקנים
import cv2  # עבור תצוגה ועריכה של תמונות וידאו
import pandas as pd  # עבור עבודה עם נתונים בטבלאות (כמו עם מיקום הכדור)
import pickle  # עבור שמירה וטעינה של נתונים מוקטבים
import supervision as s  # לצורך שימוש בפונקציות מעקב
import numpy as np
from flask import Flask, request, send_from_directory, jsonify
from threading import Thread

app = Flask(__name__)
OUTPUT_FOLDER = 'output_videos'

@app.route('/video/<filename>')
def serve_video(filename):
    return send_from_directory(OUTPUT_FOLDER, filename)
def run_flask_server():
    app.run(host='0.0.0.0', port=8000)
def process_video(input_path, output_path):
    print("iijijijiji")
    print("Processing video...")
    print("huhuu")
    video_frames = read_video_file(input_path)
    print("ht")
    tracker = Tracker('models/best.pt')
    print("j")
    tracks = tracker.get_object_tracks(video_frames, read_from_stub=True, stub_path='stubs/track_stubs.pkl')
    print("k")
    tracker.add_position_to_tracks(tracks)
    print(f"Number of players in first frame: {len(tracks['player'][0])}")


    camera_movment_estimator = CameraMovmentEstimator(video_frames[0])
    camera_movment_per_frame = camera_movment_estimator.get_camera_movment(video_frames, read_from_stub=True, stub_path='stubs/camera_movment_stub.pkl')
    camera_movment_estimator.add_adjust_positions_to_tracks(tracks, camera_movment_per_frame)

    view_transformer = ViewTransformer()
    view_transformer.add_transformed_position_to_tracks(tracks)

    tracks["ball"] = tracker.interpolate_ball_positions(tracks["ball"])

    speed_and_distance_estimator = SpeedAndDistance_Estimator()
    speed_and_distance_estimator.add_speed_and_distance_to_tracks(tracks)

        # קביעת צבעי הקבוצות
    team_assigner = TeamAssigner()
    team_assigner.assign_team_color(video_frames[0], tracks['player'][0])
    for frame_num, player_track in enumerate(tracks['player']):
        for player_id, track in player_track.items():
            team = team_assigner.get_player_team(
            video_frames[frame_num],
            track['bbox'],
            player_id
        )
            tracks['player'][frame_num][player_id]['team'] = team
            tracks['player'][frame_num][player_id]['team_color'] = team_assigner.team_colors[team]
###

    # ניהול מסירות ותרגול ניתוח השחקנים
    pass_counter = PassCounter(team_assigner)
    player_assigner = PlayerBallAssigner()
    
    team_ball_control = []

    for frame_num, player_track in enumerate(tracks['player']):
        ball_bbox = tracks['ball'][frame_num][1]['bbox']
        assigned_player = player_assigner.assign_ball_to_player(player_track, ball_bbox)

        if assigned_player != -1:
            print("hello")
            player_data = tracks['player'][frame_num][assigned_player]

            if 'team' in player_data:
                player_data['has_ball'] = True
                current_team = player_data.get('team')

            # נכניס רק אם יש מפתח תקין
                team_ball_control.append(current_team)

                if current_team is not None and int(current_team) in [0, 1]:
                    pass_counter.count_pass(player_track, ball_bbox, frame_num)
                else:
                    print(f"Warning: 'team' key missing or invalid for player {assigned_player} in frame {frame_num}")
            else:
                print(f"Warning: 'team' key missing for player {assigned_player} in frame {frame_num}")
                team_ball_control.append(team_ball_control[-1] if team_ball_control else None)
        else:
        # לא נמצא שחקן שהכדור אצלו
            team_ball_control.append(team_ball_control[-1] if team_ball_control else None)

    team_ball_control = np.array(team_ball_control)


    # שמירת הסרטון המנותח
    output_video_frames = tracker.draw_annotations(video_frames, tracks, team_ball_control)
    output_video_frames = camera_movment_estimator.draw_camera_movment(output_video_frames, camera_movment_per_frame)
    speed_and_distance_estimator.draw_speed_and_distance(output_video_frames, tracks)

    save_video(output_video_frames, output_path, codec='mp4v')
    print(f"Processed video saved as {output_path}")

def stream_video_to_client(video_path, client):
    print("Starting video stream to client...")
    cap = cv2.VideoCapture(video_path)

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        # קידוד הפריים ל-JPEG
        success, encoded_image = cv2.imencode('.jpg', frame)
        if not success:
            continue

        data = encoded_image.tobytes()
        size = len(data)

        # שליחת אורך הפריים ואחריו הנתונים
        client.sendall(struct.pack('>I', size))
        client.sendall(data)

    cap.release()
    print("Video stream finished.")


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("localhost", 9999))
    server.listen(1)
    print("Server listening on port 9999...")

    while True:
        client, addr = server.accept()
        print(f"Connection from {addr}")
        received = client.recv(1024).decode().strip()
        file_name, file_size_data = received.split("<SEPARATOR>")
        file_size = int(file_size_data)

        print(f"Received file name: {file_name}")

        if not file_size_data.isdigit():
            print("Error: Invalid file size received.")
            client.close()
            continue
        print(f"File size: {file_size} bytes")

        client.sendall(b"ACK")

        video_data = b""
        progress = tqdm.tqdm(unit="B", unit_scale=True, unit_divisor=1000, total=file_size)
        while len(video_data) < file_size:
            chunk = client.recv(4096)
            if not chunk:
                break
            video_data += chunk
            progress.update(len(chunk))

        with open("received_video.mp4", "wb") as f:
            f.write(video_data)
        print("Video received. Processing...")

        output_path = "output_videos/output_video1.avi"
        process_video("received_video.mp4", output_path)

        # שליחת URL במקום סטרימינג ישיר
        client.sendall(b"http://localhost:8000/video/output_video1.avi")

        print("Finished sending processed video URL. Closing connection.")
        client.close()

if __name__ == "__main__":
    flask_thread = Thread(target=run_flask_server)
    flask_thread.daemon = True
    flask_thread.start()

    main()
