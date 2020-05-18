"""module for tracking game state
"""
import random
import math
import uuid
import datetime
import scoredice
import player

class GameState:
    """Track the game state for farkle game
    """
    _goallevels = [5000, 8000, 10000, 12000, 15000, 20000, 25000, 30000]

    def __init__(self):
        self.uniqID = str(uuid.uuid4())

        # our current roll.
        self.turn = TurnState()

        # our completed turns for this game
        self.turns = []

        # how much wagered this game.
        self.turnBet = 0

        # what mode are we playing?
        self.gameMode = "NORMAL"

        # what step are we in on the tutorial
        self.tutorialStep = 0


        # coins won on last turn
        self.won = 0

        # total coins won this game
        self.wonGame = 0

        # True if we just earned bonus boost dice
        self.boostBonus = False

        # True if game is over
        self.gameOver = True

        # True if extra roll been used this game
        self.hasExtra = False
        # True if we used 2X on this game
        self.hasDoubled = False
        # True if undo been used this turn
        self.hasUndone = False

        # the level we want to attain (next)
        self._goal = 0
        # a message to return
        self.message = None
        # player id session is for
        self.player_id = None


        # GAME PROPERTIES
        # number of coins in the jackpot
        self.jackpot = 0
        self.game_adjust = {}

        # PLAYER PROPERTIES
        # player coin balance
        self.balance = 0
        # the number of boost dice available
        self.numBoosts = 0
        # num gems
        self.numGems = 0
        # total amount bet
        self.amountBet = 0
        # the number of coins won NOT COUNTING POWERUPs
        # So, Extra roll is not counted, point double is not counted
        # and a farkle sets the turn to be 0, so anything after undoing
        # a farkle is not counted.
        self.amountEarned = 0
        # number of turns played ever
        self.numTurns = 0
        self.last_bonus = ''
        self.player_adjustments = {}

    def init_dict(self, dct):
        """Initialize this object from a dictionary. Used when deserializing
        """
        for key in dct.keys():
            setattr(self, key, dct[key])

    def get_save_dict(self):
        """gather all the properties to save to the db
        """
        return {
            'uniqID': self.uniqID,
            'turn': self.turn.get_save_dict(),
            'turns': [t.get_save_dict() for t in self.turns],
            'turnBet': self.turnBet,
            'gameMode': self.gameMode,
            'tutorialStep': self.tutorialStep,
            'won': self.won,
            'wonGame': self.wonGame,
            'boostBonus': self.boostBonus,
            'gameOver': self.gameOver,
            'hasExtra': self.hasExtra,
            'hasDoubled': self.hasDoubled,
            'hasUndone': self.hasUndone,
            '_goal': self._goal,
            'player_id': self.player_id
        }

    def update_from_player(self, player_1: player.Player):
        """get info from player object and update our state
        """
        self.player_id = player_1.player_id
        self.balance = player_1.num_credits
        self.numGems = player_1.num_gems
        if 'num_farkle_boosts' in player_1.farkle:
            self.numBoosts = player_1.farkle['num_farkle_boosts']
        if 'amount_won' in player_1.farkle:
            self.amountEarned = player_1.farkle['amount_won']
        if 'amount_bet' in player_1.farkle:
            self.amountBet = player_1.farkle['amount_bet']
        if 'games_played' in player_1.farkle:
            self.numTurns = player_1.farkle['games_played']
        if 'last_bonus' in player_1.farkle:
            self.last_bonus = player_1.farkle['last_bonus']

    def update_from_game(self, game):
        """get info from game object and update our state. Mainly the jackpot
        """
        if 'jackpot' in game:
            self.jackpot = game['jackpot']



    # begin a new turn
    def start_turn(self, bet):
        """Called to begin a new turn in farkle. This may or may not be a new game.
        """
        if not self.end_roll():
            return False

        # need new object for multi-turn games
        self.turn = TurnState()

        if self.gameOver:
            self.numTurns = self.numTurns + 1
            self.player_adjustments['farkle.games_played'] = 1
            self.turnBet = bet

            #
            # check for boosts
            #
            if self.last_bonus == '':
                # get initial boosts
                self.player_adjustments['farkle.last_bonus'] = str(datetime.datetime.now())
                self.player_adjustments['farkle.num_farkle_boosts'] = 20
                self.numBoosts += 20
            elif (datetime.datetime.now() - \
                    datetime.datetime.strptime(self.last_bonus, \
                        "%Y-%m-%d %H:%M:%S.%f")).total_seconds() > 24*60*60:
                # get free boosts every 24 hours
                self.player_adjustments['farkle.last_bonus'] = str(datetime.datetime.now())
                self.player_adjustments['farkle.num_farkle_boosts'] = 3
                self.numBoosts += 3
                self.boostBonus = True

            if self.gameMode == "LONG":
                # start at initial level
                self._goal = 0
            if self.gameMode != "TUTORIAL":
                self.amountBet += bet
                self.balance -= bet
                self.player_adjustments['farkle.amount_bet'] = bet
                self.player_adjustments['num_credits'] = -bet
                self.jackpot += math.floor(bet/10)
                self.game_adjust['jackpot'] = math.floor(bet/10)
                if self.balance < 0:
                    # replenish
                    self.balance += bet*5
                    self.player_adjustments['num_credits'] += bet*5
            else:
                self.tutorialStep = 1
            self.turns.clear()
            self.turn.reset_game()
            self.wonGame = 0
            self.won = 0
            self.hasDoubled = False
            self.hasExtra = False
            self.hasUndone = False
            self.gameOver = False
            self.message = "new game"
        else:
            self.turn.reset_turn()
            self.message = "next turn in game"

        return True


    # roll dice for current turn, holding the given dice for points.
    # @hold - array of indices of the dice held. Indices into the list of dice in TurnState
    # @extra - if True, roll all 6 dice and use the extra roll powerup.
    def roll(self, hold, extra):
        """  roll dice for current turn, holding the given dice for points.
             @hold - array of indices of the dice held. Indices into the list of dice in TurnState
             @extra - if True, roll all 6 dice and use the extra roll powerup.
        """
        if self.gameOver:
            self.message = "game not started"
        elif self.turn.rolled and self.turn.farkle and not self.turn.unfarkled:
            self.message = "cannot roll after farkle"
            return False
        elif self.turnBet == 0:
            self.message = "cannot roll without a bet"
            return False

        # check if we need to start (save a call). This allows us to go from
        # end_turn to roll in a LONG game, without a START in between.
        if self.turn.rolled == false and self.turn.freshRolls > 0:
            # we must be in a long game since game not over and turnBet is set but we haven't
            if not self.start_turn(self.turnBet)
                return False
        
        if not self.end_roll(hold):
            return False
        
        
        if self.gameMode == "TUTORIAL":  # put after endRoll to set up roll appropriately.
            #
            # check the hold is correct for our turn number
            #
            if self.tutorialStep < 6:
                # roll
                self.turn.roll_tutorial(self.tutorialStep)
                self.tutorialStep += 1
                self.message = "tutorial progress"
        # if we want to use extra roll, and we have one, and we aren't rolling
        # all dice anyway, then use extraroll.
        elif extra and not self.hasExtra and self.numBoosts > 0 and self.turn.diceRolled < 6:
            self.message = "extra roll"
            self.numBoosts -= 1
            self.player_adjustments['farkle.num_farkle_boosts'] = -1
            self.turn.extra_roll()
        else:
            screws = 1.0
            if self.numTurns > 10 and self.amountEarned > 5000:
                # calculate average win
                ratio = (self.amountBet / self.amountEarned)*0.9  # target 90%
                if ratio > 2.5:
                    ratio = 2.5
                elif ratio < 0.5:
                    ratio = 0.5
                screws = ratio
            elif self.amountEarned == 0:
                screws = 3.0
            self.message = "rolling %s dice" % self.turn.diceRolled
            self.turn.roll(screws)

        score = scoredice.ScoreDice(self.turn.dice)
        self.turn.farkle = score.total_points == 0
        if self.turn.farkle:
            self.turn.set_points(0)

        if self.turn.hasDoubled:
            self.hasDoubled = True
        if self.turn.hasExtra:
            self.hasExtra = True
        if self.turn.hasUndone:
            self.hasUndone = True

        return True

    def goalAmount(self):
        """calculate the amount needed to continue winning
        """
        if self._goal >= len(GameState._goallevels):
            return GameState._goallevels[len(GameState._goallevels)-1] \
                + 10000 * (self._goal-len(GameState._goallevels)+1)
        return GameState._goallevels[self._goal]

    def gameScore(self):
        """calculate the total game score by summing all the completed turns
        """
        return sum([turn.points for turn in self.turns])

    # complete a turn, take points and ready to start a new turn.
    def end_turn(self, hold=None, double_it=False):
        """Finish the current turn. Do not roll again. Hold the dice that are given.
        """
        if not self.end_roll(hold, True):
            return False

        # check if we have 3 farkles!
        if self.turn.farkle and not self.turn.unfarkled and len(self.turns) >= 2:
            # see if we've got 3 farkles in a row
            turn1 = self.turns[len(self.turns)-1]
            turn2 = self.turns[len(self.turns)-2]
            if turn1.farkle and not turn1.unfarkled and turn1.points == 0 \
                and turn2.farkle and not turn2.unfarkled and turn2.points == 0:
                self.turn.points = -500


        # save the results of the turn
        self.turns.append(self.turn)

        if double_it and self.numBoosts > 0 and not self.hasDoubled:
            self.player_adjustments['farkle.num_farkle_boosts'] = -1
            self.numBoosts -= 1
            self.turn.double_it()
            self.hasDoubled = True

        if self.turn.points >= 10000:
            # get the jackpot!!!
            self.game_adjust['jackpot'] = -self.jackpot + 10000
            self.player_adjustments['num_credits'] = self.jackpot
            self.balance += self.jackpot
            self.jackpot = 1000
        else:
            self.player_adjustments['num_credits'] = 0

        earned_this_game = 0
        if self.gameMode == "LONG":
            total = self.gameScore()
            self.won = 0
            while total >= self.goalAmount():
                self.won += self.turnBet
                self._goal += 1
            self.wonGame += self.won
            self.balance += self.won

            self.gameOver = len(self.turns) == 10
            if self.gameOver:
                earned_this_game = math.floor(self._goal * self.turnBet)
        else:
            if self.gameMode != "TUTORIAL":
                earned_this_game = math.floor(self.turn.unboostedPoints * self.turnBet/500)

            self.wonGame = self.won = math.floor(self.turn.points * self.turnBet/500)
            self.balance += self.won
            self.gameOver = True

        # not eligible to roll until we bet
        if self.gameOver:
            # don't actually change the game balance until the game ends
            self.player_adjustments['num_credits'] += self.wonGame
            self.amountEarned += earned_this_game
            self.player_adjustments['farkle.amount_won'] = earned_this_game
            self.turnBet = 0

        return True

    # if roll is farkled, undo it. Can only be done once per turn.
    def unfarkle(self):
        """undo a farkle that just happened
        """
        if self.gameMode == "TUTORIAL":
            self.turn.unroll()
        elif self.turn.farkle and self.numBoosts > 0 and not self.hasUndone:
            self.numBoosts -= 1
            self.player_adjustments['farkle.num_farkle_boosts'] = -1
            self.turn.unroll()
            self.hasUndone = True
        else:
            self.message = "cannot unfarkle"
            return False

        return True


    def buy_boosts(self, gems):
        """buy boosts using gems from player account
        """
        if self.numGems < gems:
            return False
        self.player_adjustments['num_gems'] = -gems
        self.numGems -= gems
        num_to_add = 0
        while gems >= 10:
            num_to_add += 50
            gems -= 10
        while gems >= 5:
            num_to_add += 20
            gems -= 5
        while gems >= 1:
            num_to_add += 3
            gems -= 1
        self.player_adjustments['farkle.num_farkle_boosts'] = num_to_add
        self.numBoosts += num_to_add
        return True



    # internal function called when rolling or ending turn.
    def end_roll(self, hold=None, ending_turn=False):
        """called internally when a new roll or end of turn happens, to apply points
           from the most recent roll
        """
        if self.turn.rolled:
            if not ending_turn and not self.turn.farkle and (hold is None or len(hold) == 0):
                # cannot end roll without holding any dice, unless it was a farkle
                self.message = "no dice held"
                return False

            #
            # score the held dice and add to turn points
            #
            if not hold is None and len(hold) > 0:
                if self.turn.farkle:
                    self.message = "held after farkle not allowed"
                    return False # cannot hold anything after farkle (makes no sense?)

                # score the dice held
                held = list(map(lambda i: self.turn.dice[i], hold))
                score = scoredice.ScoreDice(held)
                # if any dice not used, return False
                if False in score.dice_used:
                    print(score.__dict__)
                    self.message = "invalid dice held"
                    return False

                self.turn.add_points(score.total_points)
                # set how many dice to roll next time.
                self.turn.diceRolled -= len(hold)
                if self.turn.diceRolled == 0:
                    # roll them all!
                    self.turn.diceRolled = 6

            self.turn.rolled = False

        return True


class TurnState:
    """track the state of the current turn
    """
    def __init__(self):
        # the points earned before power up used.
        self.unboostedPoints = 0
        # number of points that have been locked by being held
        self.points = 0
        # points before the farkle happened for undoing
        self.savePoints = 0
        # the number of dice to roll/rolled
        self.diceRolled = 0
        # the dice values rolled.  1 for ONE, 6 for SIX (no zeros)
        self.dice = []
        # True if dice have been rolled
        self.rolled = False
        # True if this roll is a farkle
        self.farkle = False
        # True if undo been used this turn
        self.hasUndone = False
        # True if undo has been used this ROLL
        # (we need to know if we farkled and also if it's undone)
        self.unfarkled = False
        # True if extra roll been used this turn
        self.hasExtra = False
        # True if we used 2X on this turn
        self.hasDoubled = False
        # number of times we have rolled all 6 dice this turn
        self.freshRolls = 0
        self.reset_game()

    def init_dict(self, dct):
        """Initialize this object from a dictionary. Used when deserializing
        """
        for key in dct.keys():
            setattr(self, key, dct[key])

    def get_save_dict(self):
        """get the dictionary to save for the state of this turn
        """
        return self.__dict__

    def reset_game(self):
        """reset for a new game, which may have multiple turns
        """
        self.hasUndone = False
        self.hasExtra = False
        self.hasDoubled = False
        self.reset_turn()

    def reset_turn(self):
        """reset state for a new turn
        """
        self.points = 0
        self.diceRolled = 6
        self.freshRolls = 0
        self.unfarkled = False
        self.rolled = False
        self.farkle = False



    def roll_tutorial(self, step):
        """Generate a roll when in tutorial mode. Always the same rolls.
        """
        if step == 1:
            self.dice = [1, 2, 5, 3, 3, 6]  # 1 and 5
            self.diceRolled = 6
            self.farkle = False
        elif step == 2:
            self.dice = [4, 2, 2, 2]  # 3 2s
            self.diceRolled = 4
            self.farkle = False
        elif step == 3:
            self.dice = [6]  # farkle
            self.diceRolled = 1
            self.farkle = True
        elif step == 4:
            # undo farkle and extra roll
            self.unfarkled = True
            self.hasUndone = True
            self.hasExtra = True
            self.diceRolled = 6
            self.dice = [1, 2, 3, 4, 5, 6]  # straight
        elif step == 5:
            # hot dice!
            self.dice = [3, 4, 4, 2, 4, 4] # 4 4s
            self.diceRolled = 6
        #
        self.rolled = True


    def roll(self, screws=1.0):
        """Randomly set our dice values
           screws: if 1.0, the rolls are completely random. > 1.0 the odds of
           rolling a 1 increase. < 1.0 the odds of rolling a 1 decrease.
        """
        self.farkle = False
        self.unfarkled = False
        if self.diceRolled == 6:
            self.freshRolls = self.freshRolls + 1
        self.dice = list(map(lambda x: self.rand(screws), range(self.diceRolled)))
        self.rolled = True

    def unroll(self):
        """undo the farkle roll previously
        """
        if not self.hasUndone:
            self.hasUndone = True
            self.unfarkled = True
            self.points = self.savePoints  # unboosted should stay at 0

    def extra_roll(self):
        """called from gamestate when extra roll is used during roll function
        """
        if not self.hasExtra:
            self.diceRolled = 6
            self.hasExtra = True
            self.roll()

    def double_it(self):
        """If we haven't already used our 2X powerup this turn
           use it now
        """
        if not self.hasDoubled:
            self.add_points(self.points)
            self.hasDoubled = True

    def add_points(self, points_to_add):
        """used internally to add points to the current turn. This happens
            when dice are held and roll again or turn ends.
        """
        self.points += points_to_add
        if not self.hasExtra and not self.hasUndone and not self.hasDoubled:
            self.unboostedPoints = self.points

    def set_points(self, points_to_set):
        """set the points. In case of a farkle, this is used to set score to 0,
           and then back when unfarkled
        """
        self.savePoints = self.points
        self.points = points_to_set
        if (not self.hasExtra and not self.hasUndone):
            self.unboostedPoints = self.points

    def rand(self, screws):
        """return single int between 1 and 6 inclusive, which is
           weighted by screws. The higher screws, the more likely
           to return 1
        """
        frandom = random.random()
        boundary = (1.0/scoredice.ScoreDice.SIDES)*screws
        # screws for the one
        if frandom <= boundary:
            return 1
        # all others even chance
        random_face = math.floor((frandom-boundary) * (scoredice.ScoreDice.SIDES-1) /
                                 (1.0 - boundary)) + 2
        if random_face > 6:
            random_face = 6 # one tiny edge case with rounding possible
        return random_face
