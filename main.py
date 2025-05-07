import socket
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

# פונקציה לקרוא את הסרטון ולוודא שהוא קובץ וידאו
def read_video_file(file_path):
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Video file not found: {file_path}")
    video_frames = read_video(file_path)
    if video_frames is None:
        raise ValueError(f"Unable to process video file: {file_path}")
    return video_frames

def main():
    # יצירת חיבור לשרת
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('localhost', 65432))
    server_socket.listen(1)
    print("Server is listening...")

    conn, addr = server_socket.accept()
    print(f"Connected by {addr}")

    # קבלת מידע בסיסי מהלקוח
    metadata = conn.recv(1024).decode('utf-8').split(',')
    file_size, team1_name, team2_name, team1_color, team2_color = metadata
    conn.sendall(b'ACK')

    # קבלת הקובץ מהלקוח
    video_data = b''
    while len(video_data) < int(file_size):
        video_data += conn.recv(4096)

    # שמירת הקובץ שהתקבל
    with open("received_video.mp4", 'wb') as f:
        f.write(video_data)
    print("Video received.")

    # קריאת הסרטון וניתוחו
    video_frames = read_video_file("received_video.mp4")
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

    # ניהול מסירות ותרגול ניתוח השחקנים
    pass_counter = PassCounter(team_assigner)
    player_assigner = PlayerBallAssigner()
    
    team_ball_control = []
    for frame_num, player_track in enumerate(tracks['player']):
        ball_bbox = tracks['ball'][frame_num][1]['bbox']
        assigned_player = player_assigner.assign_ball_to_player(player_track, ball_bbox)

        if assigned_player != -1:
            player_data = tracks['player'][frame_num][assigned_player]
            current_team = player_data.get('team')
            if current_team is not None and int(current_team) in [0, 1]:
                team_ball_control.append(int(current_team))
                pass_counter.count_pass(player_track, ball_bbox, frame_num)
            else:
                print(f"Warning: 'team' key missing for player {assigned_player} in frame {frame_num}")
        else:
            team_ball_control.append(team_ball_control[-1] if team_ball_control else None)

    clean_passes = {team: count for team, count in pass_counter.passes_count.items() if team in [0, 1]}

    # שמירת הסרטון המנותח
    output_video_frames = tracker.draw_annotations(video_frames, tracks, team_ball_control)
    output_video_frames = camera_movment_estimator.draw_camera_movment(output_video_frames, camera_movment_per_frame)
    speed_and_distance_estimator.draw_speed_and_distance(output_video_frames, tracks)
    
    processed_video_path = 'output_videos/output_video1.avi'
    save_video(output_video_frames, processed_video_path)
    print(f"Processed video saved at {processed_video_path}")

    # שמירה למסד נתונים של נתוני הקבוצות
    team_mapping = {0: (team1_name, team1_color), 1: (team2_name, team2_color)}
    for team, passes in clean_passes.items():
        team_name, team_color = team_mapping[team]
        save_team_data(team_name, team_color, passes)
        print(f"Saved data for {team_name} - Color: {team_color}, Passes: {passes}")

    conn.close()

def save_team_data(team_name, team_color, passes):
    conn = sqlite3.connect('soccer_analysis.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS team_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_name TEXT,
            team_color TEXT,
            passes INTEGER
        )
    ''')
    cursor.execute('''
        INSERT INTO team_stats (team_name, team_color, passes)
        VALUES (?, ?, ?)
    ''', (team_name, team_color, passes))
    conn.commit()
    conn.close()

if __name__ == '__main__':
    main()