# server_2.py
import socket
import tqdm
import os
import sqlite3
import numpy as np
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
# Initialize the server
def read_video_file(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Video file not found: {file_path}")
    video_frames = read_video(file_path)
    if video_frames is None:
        raise ValueError(f"Unable to process video file: {file_path}")
    return video_frames
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind(("localhost", 9999))
server.listen(1)  # Allow one connection at a time
print("Server listening on port 9999...")

# Accept the connection
client, addr = server.accept()
print(f"Connection from {addr}")

# Receive file name from client
file_name = client.recv(1024).decode()
print(f"Receiving file: {file_name}")

# Receive file size from client
file_size = client.recv(1024).decode()
if not file_size.isdigit():
    print("Error: Invalid file size received.")
    client.close()
    server.close()
    exit()
file_size = int(file_size)
print(f"File size: {file_size} bytes")

# Send acknowledgment to the client
client.send("ACK".encode())

# Open a file to write the received data
file_path = os.path.join(file_name)
with open(file_path, "wb") as file:
    progress = tqdm.tqdm(unit="B", unit_scale=True, total=file_size)
    received_size = 0
    while received_size < file_size:
        data = client.recv(4096)
        if not data:
            break
        file.write(data)
        received_size += len(data)
        progress.update(len(data))

print(f"File {file_name} received successfully!")
# קריאת הסרטון וניתוחו
video_frames = read_video_file(file_name)
tracker = Tracker('models/best.pt')
tracks = tracker.get_object_tracks(video_frames, read_from_stub=True, stub_path='stubs/track_stubs.pkl')
tracker.add_position_to_tracks(tracks)
    
    # הערכת תנועת המצלמה
camera_movment_estimator = CameraMovmentEstimator(video_frames[0])
camera_movment_per_frame = camera_movment_estimator.get_camera_movment(video_frames, read_from_stub=True, stub_path='stubs/camera_movment_stub.pkl')
camera_movment_estimator.add_adjust_positions_to_tracks(tracks, camera_movment_per_frame)
    
    # שינוי מיקום נקודות
view_transformer = ViewTransformer()
view_transformer.add_transformed_position_to_tracks(tracks)
    
    # אינטרפולציה למיקומים של הכדור
tracks["ball"] = tracker.interpolate_ball_positions(tracks["ball"])
    
    # חישוב מהירות ומרחק של השחקנים
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

# כמות מסירות של כל קבוצה
    if assigned_player != -1:
        tracks['player'][frame_num][assigned_player]['has_ball'] = True
        team_ball_control.append(tracks['player'][frame_num][assigned_player]['team'])
        player_data = tracks['player'][frame_num][assigned_player]
        current_team = player_data.get('team')
        if current_team is not None and int(current_team) in [0, 1]:
            team_ball_control.append(int(current_team))
            pass_counter.count_pass(player_track, ball_bbox, frame_num)
        else:
            print(f"Warning: 'team' key missing for player {assigned_player} in frame {frame_num}")
    else:
        team_ball_control.append(team_ball_control[-1] if team_ball_control else None)
team_ball_control = np.array(team_ball_control)

clean_passes = {team: count for team, count in pass_counter.passes_count.items() if team in [0, 1]}

    # שמירת הסרטון המנותח
output_video_frames = tracker.draw_annotations(video_frames, tracks, team_ball_control)
output_video_frames = camera_movment_estimator.draw_camera_movment(output_video_frames, camera_movment_per_frame)
speed_and_distance_estimator.draw_speed_and_distance(output_video_frames, tracks)
    
processed_video_path = 'output_videos/output_video1.avi'
save_video(output_video_frames, processed_video_path)
print(f"Processed video saved at {processed_video_path}")

# Close the client and server connections
client.close()
server.close()
