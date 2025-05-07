import sys
import socket
import struct
import cv2
import os
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QPushButton, QVBoxLayout, QFileDialog, QWidget)
from PyQt5.QtGui import QFont, QImage, QPixmap
from PyQt5.QtCore import Qt, QTimer
import tqdm
from PyQt5.QtWidgets import QSizePolicy

from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtCore import QUrl
from PyQt5.QtWidgets import QSlider, QHBoxLayout
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
class SoccerAnalysisApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Soccer Analysis App")
        self.setGeometry(100, 100, 900, 650)
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

        self.player = QMediaPlayer()
        self.player.setVideoOutput(self.video_widget)


        self.player = QMediaPlayer(None, QMediaPlayer.VideoSurface)
        self.video_widget = QVideoWidget()
        self.player.setVideoOutput(self.video_widget)
        layout.addWidget(self.video_widget)

# פס זמן
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 0)
        self.slider.sliderMoved.connect(self.player.setPosition)
        layout.addWidget(self.slider)

# עדכון פס זמן תוך כדי ניגון
        self.player.positionChanged.connect(self.slider.setValue)
        self.player.durationChanged.connect(lambda duration: self.slider.setRange(0, duration))
        # כפתורי שליטה
        controls_layout = QHBoxLayout()

        self.play_btn = QPushButton("▶️ Play")
        self.play_btn.clicked.connect(self.player.play)
        controls_layout.addWidget(self.play_btn)

        self.pause_btn = QPushButton("⏸ Pause")
        self.pause_btn.clicked.connect(self.player.pause)
        controls_layout.addWidget(self.pause_btn)

        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.clicked.connect(self.player.stop)
        controls_layout.addWidget(self.stop_btn)

        self.backward_btn = QPushButton("⏪ Back 5s")
        self.backward_btn.clicked.connect(lambda: self.player.setPosition(self.player.position() - 5000))
        controls_layout.addWidget(self.backward_btn)

        self.forward_btn = QPushButton("⏩ Fwd 5s")
        self.forward_btn.clicked.connect(lambda: self.player.setPosition(self.player.position() + 5000))
        controls_layout.addWidget(self.forward_btn)

        layout.addLayout(controls_layout)


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
            stream_url = url_data.decode().strip()
            print(f"🎬 Video URL received: {stream_url}")
            self.player.setMedia(QMediaContent(QUrl(stream_url)))
            self.player.play()
        except Exception as e:
            print(f"❌ Error during receiving URL: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = SoccerAnalysisApp()
    main_window.show()
    sys.exit(app.exec_())
