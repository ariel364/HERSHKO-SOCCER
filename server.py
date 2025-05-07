import socket
import os
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


class SoccerAnalysisServer:
    def __init__(self, host='localhost', port=65432):
        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(1)
        print(f"Server is listening on {self.host}:{self.port}")

    def handle_client(self, client_socket):
        try:
            # קבלת מידע (metadata) מהלקוח
            metadata = client_socket.recv(1024).decode('utf-8')
            print(f"Received metadata: {metadata}")
            
            # שליחה של אישור שהלקוח קיבל את המידע
            client_socket.sendall(b"Metadata received")
            
            # קבלת קובץ הווידאו
            with open("received_video.mp4", 'wb') as f:
                video_data = client_socket.recv(1024)
                while video_data:
                    f.write(video_data)
                    video_data = client_socket.recv(1024)
                print("Video received successfully!")
            
            # שליחת אישור על קבלת הווידאו
            client_socket.sendall(b"Video received successfully")

            # קריאת הווידאו
            video_frames = read_video("received_video.mp4")

            # Initialize Tracker
            tracker = Tracker('models/best.pt')
            tracks = tracker.get_object_tracks(video_frames, read_from_stub=True, stub_path='stubs/track_stubs.pkl')
            tracker.add_position_to_tracks(tracks)

            # Camera movement estimator
            camera_movment_estimator = CameraMovmentEstimator(video_frames[0])
            camera_movment_per_frame = camera_movment_estimator.get_camera_movment(video_frames,
                                                                               read_from_stub=True,
                                                                               stub_path='stubs/camera_movment_stub.pkl')
            camera_movment_estimator.add_adjust_positions_to_tracks(tracks, camera_movment_per_frame)

            # View Transformer
            view_transformer = ViewTransformer()
            view_transformer.add_transformed_position_to_tracks(tracks)

            # Interpolate ball positions
            tracks["ball"] = tracker.interpolate_ball_positions(tracks["ball"])

            # Speed and distance
            speed_and_distance_estimator = SpeedAndDistance_Estimator()
            speed_and_distance_estimator.add_speed_and_distance_to_tracks(tracks)

            # Assign Player Teams
            team_assigner = TeamAssigner()
            team_assigner.assign_team_color(
                video_frames[0],
                tracks['player'][0]
            )

            for frame_num, player_track in enumerate(tracks['player']):
                for player_id, track in player_track.items():
                    team = team_assigner.get_player_team(video_frames[frame_num], track['bbox'], player_id)
                    tracks['player'][frame_num][player_id]['team'] = team
                    tracks['player'][frame_num][player_id]['team_color'] = team_assigner.team_colors[team]

            # Assign ball acquisition
            player_assigner = PlayerBallAssigner()
            team_ball_control = []  # 0 or 1 for each team
            pass_counter = PassCounter(team_assigner)

            for frame_num, player_track in enumerate(tracks['player']):
                ball_bbox = tracks['ball'][frame_num][1]['bbox']
                assigned_player = player_assigner.assign_ball_to_player(player_track, ball_bbox)

                if assigned_player != -1:
                    tracks['player'][frame_num][assigned_player]['has_ball'] = True
                    current_team = int(tracks['player'][frame_num][assigned_player]['team'])

                    if current_team in [0, 1]:
                        team_ball_control.append(current_team)
                        pass_counter.count_pass(player_track, ball_bbox, frame_num)
                        print(f"Frame {frame_num}: Ball is with Player {assigned_player} of Team {current_team}")
                else:
                    if team_ball_control:
                        team_ball_control.append(team_ball_control[-1])
                    else:
                        team_ball_control.append(None)

            team_ball_control = np.array(team_ball_control)

            # Draw output
            output_video_frames = tracker.draw_annotations(video_frames, tracks, team_ball_control)
            output_video_frames = camera_movment_estimator.draw_camera_movment(output_video_frames, camera_movment_per_frame)

            # Draw speed and distance
            speed_and_distance_estimator.draw_speed_and_distance(output_video_frames, tracks)

            processed_video_path = 'output_videos/output_video1.avi'
            save_video(output_video_frames, processed_video_path)

            clean_passes = {team: count for team, count in pass_counter.passes_count.items() if team in [1, 2]}
            print("Pass counts per team:", clean_passes)
            pass_data = pd.DataFrame.from_dict(pass_counter.passes_count, orient='index', columns=['Passes'])
            print(pass_data)

            # שליחת הסרטון המעובד חזרה ללקוח
            with open(processed_video_path, 'rb') as f:
                video_data = f.read(1024)
                while video_data:
                    client_socket.sendall(video_data)
                    video_data = f.read(1024)
            print("Processed video sent successfully!")

        except Exception as e:
            print(f"Error: {e}")
            client_socket.sendall(b"Error during file reception")
        finally:
            client_socket.close()

    def start(self):
        while True:
            # הקשבה ללקוח חדש
            client_socket, client_address = self.server_socket.accept()
            print(f"Connection established with {client_address}")
            self.handle_client(client_socket)


if __name__ == "__main__":
    server = SoccerAnalysisServer()
    server.start()
