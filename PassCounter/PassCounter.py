from collections import defaultdict
from team_assigner import TeamAssigner
from player_ball_assigner import PlayerBallAssigner

class PassCounter:
    def __init__(self, team_assigner):
        self.passes_count = {1: 0, 2: 0}  # מסירות לכל קבוצה
        self.previous_player_with_ball = None
        self.player_ball_assigner = PlayerBallAssigner()
        self.team_assigner = team_assigner
        self.pass_graph = defaultdict(int)  # (from_id, to_id) -> count

    def count_pass(self, players, ball_bbox, frame_num):
        current_player_with_ball = self.player_ball_assigner.assign_ball_to_player(players, ball_bbox)
        print(f"Frame {frame_num}:")

        if current_player_with_ball != -1:
            current_player_bbox = players[current_player_with_ball]['bbox']
            print(f"  Current player with ball: {current_player_with_ball}")

            current_team = self.team_assigner.get_player_team(frame_num, current_player_bbox, current_player_with_ball)

            if self.previous_player_with_ball is not None and self.previous_player_with_ball in players:
                previous_player_bbox = players[self.previous_player_with_ball]['bbox']
                previous_team = self.team_assigner.get_player_team(frame_num, previous_player_bbox, self.previous_player_with_ball)

                if current_player_with_ball != self.previous_player_with_ball:
                    if current_team == previous_team:
                        self.passes_count[current_team] += 1
 
                        passer_data = players.get(self.previous_player_with_ball, {})
                        receiver_data = players.get(current_player_with_ball, {})
                        passer_id = passer_data.get("player_id", self.previous_player_with_ball)
                        receiver_id = receiver_data.get("player_id", current_player_with_ball)
                        self.pass_graph[(passer_id, receiver_id)] += 1

                        print(f"  Pass detected from Player {passer_id} to Player {receiver_id}")
                    else:
                        print(f"  Ball changed teams: {previous_team} ➝ {current_team}")
                else:
                    print(f"  Player {current_player_with_ball} is holding the ball again, no pass.")

            self.previous_player_with_ball = current_player_with_ball
            print(f"  Passes count so far: {self.passes_count}")

        return self.passes_count

