# client.py
import sys
import socket
import struct
import cv2
import os
import numpy as np
import tqdm
import pandas as pd
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QPushButton, QVBoxLayout, QFileDialog, QWidget,
    QSizePolicy, QSlider, QHBoxLayout, QDialog, QDialogButtonBox
)
from PyQt5.QtGui import QFont, QPixmap
from PyQt5.QtCore import Qt, QUrl, QTimer
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
import requests
import pyqtgraph as pg


class SoccerAnalysisApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Soccer Analysis App")
        self.setGeometry(100, 100, 900, 750)
        self.setStyleSheet("background-color: #121212;")

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        central_widget.setLayout(layout)

        self.title_label = QLabel("⚽ Welcome to Hershko Soccer Analysis ⚽")
        self.title_label.setFont(QFont("Arial", 18, QFont.Bold))
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("color: #00FF00; font-weight: bold;")
        layout.addWidget(self.title_label)

        self.upload_button = QPushButton("📂 Upload a Soccer Video")
        self.upload_button.setFont(QFont("Arial", 14))
        self.upload_button.setStyleSheet("""
        QPushButton {
            background-color: #1DB954;
            color: white;
            padding: 12px;
            border-radius: 10px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #17a74a;
        }
        QPushButton:pressed {
            background-color: #14863c;
        }
        """)
        self.upload_button.clicked.connect(self.upload_video)
        layout.addWidget(self.upload_button)

        self.video_widget = QVideoWidget()
        self.video_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.video_widget, stretch=1)

        self.player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.player.setVideoOutput(self.video_widget)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(self.player.setPosition)
        layout.addWidget(self.slider)

        self.player.positionChanged.connect(self.slider.setValue)
        self.player.durationChanged.connect(lambda duration: self.slider.setRange(0, duration))

        controls_layout = QHBoxLayout()

        def styled_button(text, slot):
            btn = QPushButton(text)
            btn.setFixedSize(100, 50)
            btn.clicked.connect(slot)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #2ea7cc;
                    color: white;
                    border-radius: 10px;
                    font-weight: bold;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #cc2e2e;
                }
            """)
            return btn

        controls_layout.addWidget(styled_button("▶️ Play", self.player.play))
        controls_layout.addWidget(styled_button("⏸ Pause", self.player.pause))
        controls_layout.addWidget(styled_button("⏹ Stop", self.player.stop))
        controls_layout.addWidget(styled_button("⏪ Back 5s", lambda: self.player.setPosition(self.player.position() - 5000)))
        controls_layout.addWidget(styled_button("⏩ Fwd 5s", lambda: self.player.setPosition(self.player.position() + 5000)))
        layout.addLayout(controls_layout)

        self.speed_plot_widget = pg.PlotWidget()
        self.speed_plot_widget.setBackground('w')
        self.speed_plot_widget.setFixedHeight(200)
        layout.addWidget(self.speed_plot_widget)

        self.server_address = ('localhost', 9999)

    def upload_video(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select a Soccer Video", "", "Video Files (*.mp4 *.avi *.mov *.mkv)")
        if file_path:
            self.send_video_to_server(file_path)

    def send_video_to_server(self, file_path):
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_socket.connect(self.server_address)

            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            client_socket.sendall(f"{file_name}<SEPARATOR>{file_size}".encode())

            ack = client_socket.recv(1024).decode()
            if ack != "ACK":
                print("Failed to receive acknowledgment from server.")
                return

            with open(file_path, 'rb') as f:
                progress = tqdm.tqdm(unit="B", unit_scale=True, total=file_size, desc="Uploading", colour="green")
                for data in iter(lambda: f.read(4096), b""):
                    client_socket.sendall(data)
                    progress.update(len(data))

            print("✅ Video sent to server successfully.")
            self.receive_video_stream(client_socket)

        except Exception as e:
            print(f"❌ Error: {e}")

    def receive_video_stream(self, client_socket):
        print("📡 Receiving video stream URL...")
        try:
            url_data = b""
            while True:
                chunk = client_socket.recv(4096)
                if not chunk:
                    break
                url_data += chunk
            stream_urls = url_data.decode().strip().split("||")

            video_path = stream_urls[0].strip()
            graph_url = stream_urls[1].strip() if len(stream_urls) > 1 else None
            csv_url = stream_urls[2].strip() if len(stream_urls) > 2 else None

            print(f"🎬 Local video path received: {video_path}")
            self.player.setMedia(QMediaContent(QUrl.fromLocalFile(video_path)))
            self.player.play()

            if graph_url:
                self.show_pass_graph_dialog(graph_url)
            if csv_url:
                self.show_speed_graph(csv_url)

        except Exception as e:
            print(f"❌ Error during receiving URL: {e}")

    def show_pass_graph_dialog(self, image_url):
        dialog = QDialog(self)
        dialog.setWindowTitle("Passing Network Graph")
        dialog.setFixedSize(720, 560)
        layout = QVBoxLayout()
        label = QLabel()
        label.setAlignment(Qt.AlignCenter)
        image = QPixmap()
        image.loadFromData(requests.get(image_url).content)
        label.setPixmap(image.scaled(700, 500, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        layout.addWidget(label)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)
        dialog.setLayout(layout)
        dialog.exec_()

    def show_speed_graph(self, csv_url):
        try:
            response = requests.get(csv_url)
            with open("temp_speed.csv", "wb") as f:
                f.write(response.content)

            df = pd.read_csv("temp_speed.csv")
            self.speed_data = df
            self.curve_dict = {}
            self.frame_num = 0

            self.timer = QTimer()
            self.timer.timeout.connect(self.update_speed_graph)
            self.timer.start(300)
        except Exception as e:
            print(f"❌ Error displaying speed graph: {e}")

    def update_speed_graph(self):
        if self.frame_num > self.speed_data['frame'].max():
            self.timer.stop()
            return

        frame_df = self.speed_data[self.speed_data['frame'] == self.frame_num]
        for _, row in frame_df.iterrows():
            player_id = row['player_id']
            speed = row['speed']
            if player_id not in self.curve_dict:
                pen = pg.mkPen(color=pg.intColor(player_id), width=2)
                self.curve_dict[player_id] = {
                    'x': [], 'y': [],
                    'plot': self.speed_plot_widget.plot([], [], pen=pen, name=str(player_id))
                }
            self.curve_dict[player_id]['x'].append(self.frame_num)
            self.curve_dict[player_id]['y'].append(speed)
            self.curve_dict[player_id]['plot'].setData(self.curve_dict[player_id]['x'], self.curve_dict[player_id]['y'])

        self.frame_num += 3


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = SoccerAnalysisApp()
    main_window.show()
    sys.exit(app.exec_())
