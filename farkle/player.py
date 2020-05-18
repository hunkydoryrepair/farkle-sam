"""module for player
"""
import uuid

class Player:
    """represents a player in our system
    """
    def __init__(self):
        self.farkle = {
            'num_farkle_boosts': 20,
            'amount_bet': 0,
            'amount_won': 0,
            'games_played': 0
        }
        self.num_gems = 20
        self.num_credits = 100000
        self.player_id = uuid.uuid4()
        self.login_key = uuid.uuid4()

    def init_dict(self, dct):
        """Initialize this object from a dictionary. Used when deserializing
        """
        for key in dct.keys():
            setattr(self, key, dct[key])
