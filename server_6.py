import socket
import tqdm
import os
import cv2
import struct
import threading
from main import read_video_file, Tracker, CameraMovmentEstimator, ViewTransformer, SpeedAndDistance_Estimator, PlayerBallAssigner, PassCounter, save_video
from PassCounter import PassCounter
from utils import save_video, read_video
from trackers import Tracker
from team_assigner import TeamAssigner
from player_ball_assigner import PlayerBallAssigner
from camera_movment_estimator import CameraMovmentEstimator
from view_transformer import ViewTransformer
from speed_and_distance_estimator import SpeedAndDistance_Estimator
import pandas as pd
import pickle
import supervision as s
import numpy as np
from flask import Flask, request, send_from_directory, jsonify
from threading import Thread
from sklearn.cluster import KMeans
from collections import defaultdict
import matplotlib.pyplot as plt

app = Flask(__name__)
OUTPUT_FOLDER = 'output_videos'

@app.route('/video/<filename>')
def serve_video(filename):
    return send_from_directory(OUTPUT_FOLDER, filename)

def run_flask_server():
    app.run(host='0.0.0.0', port=8000)

def detect_formation(tracks, team_id, frame_sample_rate=30):
    player_positions = defaultdict(list)
    for frame_num, player_track in enumerate(tracks['player']):
        if frame_num % frame_sample_rate != 0:
            continue
        for player_id, data in player_track.items():
            if data.get("team") == team_id and "transformed_position" in data:
                player_positions[player_id].append(data["transformed_position"])
    averaged_positions = []
    for player_id, positions in player_positions.items():
        if len(positions) > 0:
            avg_pos = np.mean(positions, axis=0)
            averaged_positions.append(avg_pos)
    averaged_positions = np.array(averaged_positions)
    if len(averaged_positions) < 7:
        print(f"Not enough player data to detect formation for team {team_id}")
        return
    kmeans = KMeans(n_clusters=3, random_state=0).fit(averaged_positions)
    labels = kmeans.labels_
    line_ys = [averaged_positions[labels == i][:, 1].mean() for i in range(3)]
    sorted_indices = np.argsort(line_ys)
    formation = [np.sum(labels == i) for i in sorted_indices]
    print(f"Detected formation for team {team_id}: {'-'.join(map(str, formation))}")

def save_speed_data(tracks, output_csv_path):
    rows = []
    for frame_num, player_track in enumerate(tracks['player']):
        for player_id, data in player_track.items():
            speed = data.get('speed', None)
            if speed is not None:
                rows.append({'frame': frame_num, 'player_id': player_id, 'speed': speed})
    df = pd.DataFrame(rows)
    df.to_csv(output_csv_path, index=False)

def generate_speed_graph(csv_path, output_path):
    df = pd.read_csv(csv_path)
    plt.figure(figsize=(12, 6))
    for pid in df['player_id'].unique():
        player_data = df[df['player_id'] == pid]
        plt.plot(player_data['frame'], player_data['speed'], label=f"Player {pid}")
    plt.xlabel("Frame")
    plt.ylabel("Speed")
    plt.title("Player Speeds Over Time")
    plt.legend(loc="upper right")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()

def process_video(input_path, output_path, speed_csv_path):
    print("Processing video...")
    video_frames = read_video_file(input_path)
    tracker = Tracker('models/best.pt')
    tracks = tracker.get_object_tracks(video_frames, read_from_stub=True, stub_path='stubs/track_stubs.pkl')
    tracker.add_position_to_tracks(tracks)
    camera_movment_estimator = CameraMovmentEstimator(video_frames[0])
    camera_movment_per_frame = camera_movment_estimator.get_camera_movment(video_frames, read_from_stub=True, stub_path='stubs/camera_movment_stub.pkl')
    camera_movment_estimator.add_adjust_positions_to_tracks(tracks, camera_movment_per_frame)
    view_transformer = ViewTransformer()
    view_transformer.add_transformed_position_to_tracks(tracks)
    tracks["ball"] = tracker.interpolate_ball_positions(tracks["ball"])
    speed_and_distance_estimator = SpeedAndDistance_Estimator()
    speed_and_distance_estimator.add_speed_and_distance_to_tracks(tracks)
    team_assigner = TeamAssigner()
    team_assigner.assign_team_color(video_frames[0], tracks['player'][0])
    for frame_num, player_track in enumerate(tracks['player']):
        for player_id, track in player_track.items():
            team = team_assigner.get_player_team(video_frames[frame_num], track['bbox'], player_id)
            tracks['player'][frame_num][player_id]['team'] = team
            tracks['player'][frame_num][player_id]['team_color'] = team_assigner.team_colors[team]
    pass_counter = PassCounter(team_assigner)
    player_assigner = PlayerBallAssigner()
    team_ball_control = []
    for frame_num, player_track in enumerate(tracks['player']):
        ball_bbox = tracks['ball'][frame_num][1]['bbox']
        assigned_player = player_assigner.assign_ball_to_player(player_track, ball_bbox)
        if assigned_player != -1:
            player_data = tracks['player'][frame_num][assigned_player]
            if 'team' in player_data:
                player_data['has_ball'] = True
                current_team = player_data.get('team')
                team_ball_control.append(current_team)
                if current_team is not None and int(current_team) in [0, 1]:
                    pass_counter.count_pass(player_track, ball_bbox, frame_num)
                else:
                    print(f"Warning: 'team' key missing or invalid for player {assigned_player} in frame {frame_num}")
            else:
                print(f"Warning: 'team' key missing for player {assigned_player} in frame {frame_num}")
                team_ball_control.append(team_ball_control[-1] if team_ball_control else None)
        else:
            team_ball_control.append(team_ball_control[-1] if team_ball_control else None)
    team_ball_control = np.array(team_ball_control)
    output_video_frames = tracker.draw_annotations(video_frames, tracks, team_ball_control)
    output_video_frames = camera_movment_estimator.draw_camera_movment(output_video_frames, camera_movment_per_frame)
    speed_and_distance_estimator.draw_speed_and_distance(output_video_frames, tracks)
    temp_output = f"temp_output_{threading.get_ident()}.mp4"
    save_video(output_video_frames, temp_output, codec='mp4v')
    os.system(f"ffmpeg -y -i {temp_output} -c:v libx264 -c:a aac -movflags +faststart {output_path}")
    os.remove(temp_output)
    detect_formation(tracks, team_id=0 , frame_sample_rate=5)
    detect_formation(tracks, team_id=1, frame_sample_rate=5)
    save_speed_data(tracks, speed_csv_path)
    speed_graph_path = speed_csv_path.replace(".csv", ".png")
    generate_speed_graph(speed_csv_path, speed_graph_path)
    print(f"Processed video saved as {output_path}")

def handle_client(client):
    try:
        received = client.recv(1024).decode().strip()
        file_name, file_size_data = received.split("<SEPARATOR>")
        file_size = int(file_size_data)
        print(f"Received file name: {file_name}")
        if not file_size_data.isdigit():
            print("Error: Invalid file size received.")
            client.close()
            return
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
        input_path = f"received_{threading.get_ident()}.mp4"
        output_path = f"output_videos/output_video_{threading.get_ident()}.mp4"
        speed_csv_path = f"output_videos/speed_data_{threading.get_ident()}.csv"
        with open(input_path, "wb") as f:
            f.write(video_data)
        print("Video received. Processing...")
        process_video(input_path, output_path, speed_csv_path)
        video_url = f"http://localhost:8000/video/{os.path.basename(output_path)}"
        speed_url = f"http://localhost:8000/video/{os.path.basename(speed_csv_path)}"
        speed_graph_url = f"http://localhost:8000/video/{os.path.basename(speed_csv_path).replace('.csv', '.png')}"
        client.sendall(f"{video_url}||{speed_url}||{speed_graph_url}".encode())
        print("Finished sending processed video URL. Closing connection.")
        client.close()
    except Exception as e:
        print(f"Error handling client: {e}")
        client.close()

def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("localhost", 9999))
    server.listen(5)
    print("Server listening on port 9999...")
    while True:
        client, addr = server.accept()
        print(f"Connection from {addr}")
        client_thread = Thread(target=handle_client, args=(client,))
        client_thread.start()

if __name__ == "__main__":
    flask_thread = Thread(target=run_flask_server)
    flask_thread.daemon = True
    flask_thread.start()
    main()