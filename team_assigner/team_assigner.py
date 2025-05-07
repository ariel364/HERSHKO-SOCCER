from sklearn.cluster import KMeans
import numpy as np
import cv2

class TeamAssigner:
    def __init__(self):
        self.team_colors = {}
        self.player_team_dict = {}
        self.kmeans = None

    def get_clustering_model(self, image):
        image_2d = image.reshape(-1, 3)
        kmeans = KMeans(n_clusters=2, init="k-means++", n_init=10)
        kmeans.fit(image_2d)
        return kmeans

    def get_player_color(self, frame, bbox):
        x1, y1, x2, y2 = map(int, bbox)
        image = frame[y1:y2, x1:x2]

        if image.shape[0] < 5 or image.shape[1] < 5:
            return np.array([0, 0, 0])

        top_half = image[:image.shape[0] // 2, :]
        kmeans = self.get_clustering_model(top_half)

        labels = kmeans.labels_.reshape(top_half.shape[:2])
        corners = [labels[0, 0], labels[0, -1], labels[-1, 0], labels[-1, -1]]
        non_player_cluster = max(set(corners), key=corners.count)
        player_cluster = 1 - non_player_cluster

        player_color = kmeans.cluster_centers_[player_cluster]
        return player_color

    def assign_team_color(self, frame, player_detections):
        player_colors = []
        player_ids = []

        for player_id, player_detection in player_detections.items():
            bbox = player_detection.get("bbox")
            if bbox is None:
                continue
            color = self.get_player_color(frame, bbox)
            player_colors.append(color)
            player_ids.append(player_id)

        if len(player_colors) < 2:
            print("⚠️ Not enough players to cluster teams.")
            return

        kmeans = KMeans(n_clusters=2, init="k-means++", n_init=10)
        kmeans.fit(player_colors)

        self.kmeans = kmeans
        self.team_colors[1] = kmeans.cluster_centers_[0]
        self.team_colors[2] = kmeans.cluster_centers_[1]

        # מיפוי ראשוני לפי הצבעים
        for i, player_id in enumerate(player_ids):
            team_id = kmeans.labels_[i] + 1
            self.player_team_dict[player_id] = team_id

    def get_player_team(self, frame, player_bbox, player_id):
        if player_id in self.player_team_dict:
            return self.player_team_dict[player_id]

        player_color = self.get_player_color(frame, player_bbox)

        if self.kmeans is None:
            print(f"⚠️ KMeans not initialized when trying to get team for player {player_id}")
            return None

        team_id = self.kmeans.predict(player_color.reshape(1, -1))[0] + 1
        self.player_team_dict[player_id] = team_id

        return team_id




        
            