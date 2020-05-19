"""module for player
"""
import uuid

class Player:
    """represents a player in our system
    """
    def __init__(self):
        self.farkle = {
            'num_farkle_boosts': 0,
            'amount_bet': 0,
            'amount_won': 0,
            'games_played': 0,
            'last_boost': ''
        }
        self.num_gems = 20
        self.num_credits = 100000
        self.player_id = str(uuid.uuid4())
        self.login_key = str(uuid.uuid4())
        self.username = ''
        self.password = ''
        self.displayname = ''

    def init_dict(self, dct):
        """Initialize this object from a dictionary. Used when deserializing
        """
        for key in dct.keys():
            setattr(self, key, dct[key])

    def get_save_dict(self):
        """get the attributes to write to database
        """
        return self.__dict__

    def get_client_dict(self):
        """get the values to return to client. May not want all of them
        """
        return {
            'player_id': self.player_id,
            'numBoosts': self.farkle['num_farkle_boosts'],
            'numTurns': self.farkle['games_played'],
            'numGems': self.num_gems,
            'balance': self.num_credits,
            'login_key': self.login_key,
            'username': self.username,
            'displayname': self.displayname
        }
