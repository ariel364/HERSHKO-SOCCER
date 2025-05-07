import sys
import socket
import os
import tqdm
from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QPushButton, QVBoxLayout, QFileDialog, QWidget)
from PyQt5.QtGui import QFont
from PyQt5.QtCore import Qt

class SoccerAnalysisApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Soccer Analysis App")
        self.setGeometry(100, 100, 900, 650)  # גודל חלון משופר
        self.setStyleSheet("background-color: #121212;")  # צבע כהה יותר

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout()
        layout.setSpacing(20)  # מרווחים טובים יותר
        layout.setContentsMargins(20, 20, 20, 20)
        central_widget.setLayout(layout)

        # כותרת בעיצוב משופר
        self.title_label = QLabel("⚽ Welcome to Hershko Soccer Analysis ⚽")
        self.title_label.setFont(QFont("Arial", 18, QFont.Bold))
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("color: #00FF00; font-weight: bold;")
        layout.addWidget(self.title_label)

        # כפתור שיפור גרפי
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

            client_socket.sendall(file_name.encode())
            client_socket.sendall(str(file_size).encode())

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
            client_socket.close()
        except Exception as e:
            print(f"❌ Error sending video: {e}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = SoccerAnalysisApp()
    main_window.show()
    sys.exit(app.exec_())
