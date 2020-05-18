"""This module computes the correct way to score the given dice
"""


class Payout:
    """The types of matches we can have with the dice
    """
    Kind6Of = 1
    Kind5Of = 2
    Kind4Of = 3
    Kind3Of = 4
    ThreePair = 5
    Straight6 = 6
    SumDice = 7



class ComboPoints:
    """Represents a scoring combination of dice
    """
    DICESCORES = [0, 10, 2, 3, 4, 5, 6]
    DICEVALUE = [0, 100, 0, 0, 0, 50, 0]

    def __init__(self):
        #
        # index of the dice used. Index into rolled of the scoredice class
        self.dice = []
        # number of points earned.
        self.points = 0
        # type of the payout
        self.type = Payout.Kind3Of
        # for KindOf, use this to determine score
        self.die = 1




    # apply the points for this one score.
    def apply_points(self, rolled):
        """calculate the points this combo earns
        """
        if self.type == Payout.Kind6Of:
            self.points = ComboPoints.DICESCORES[self.die] * 100 * 8
        elif self.type == Payout.Kind5Of:
            self.points = ComboPoints.DICESCORES[self.die] * 100 * 4
        elif self.type == Payout.Kind4Of:
            self.points = ComboPoints.DICESCORES[self.die] * 100 * 2
        elif self.type == Payout.Kind3Of:
            self.points = ComboPoints.DICESCORES[self.die] * 100
        elif self.type == Payout.Straight6:
            self.points = 1500
        elif self.type == Payout.ThreePair:
            self.points = 750
        elif self.type == Payout.SumDice:
            self.points = sum(ComboPoints.DICEVALUE[rolled[idx]] for idx in self.dice)


    #
    #
    @staticmethod
    def create_match(input_array, match_face):
        """ create a score with all the dice that have match as the number.

        """
        score = ComboPoints()

        score.die = match_face
        score.dice = list(\
                filter(lambda idx: input_array[idx] == match_face, range(len(input_array))))
        num_dice = len(score.dice)
        if num_dice == 6:
            score.type = Payout.Kind6Of
        elif num_dice == 5:
            score.type = Payout.Kind5Of
        elif num_dice == 4:
            score.type = Payout.Kind4Of
        elif num_dice == 3:
            score.type = Payout.Kind3Of
        else:
            score.type = Payout.SumDice
        score.apply_points(input_array)

        return score


    #
    # create a score with one of each dice that have between start and last,
    # inclusive, as their number
    # STRAIGHT constructor
    #
    @staticmethod
    def create_straight(input_array):
        """create a score with one of each dice that have between start and last,
             inclusive, as their number
                STRAIGHT constructor
    """
        score = ComboPoints()

        score.dice = [index for index in range(len(input_array))]

        score.type = Payout.Straight6
        score.apply_points(input_array)

        return score

    @staticmethod
    def create_three_pairs(input_array):
        """create a score with all the dice that have match1 or match2 as the number,
            for fullhouse or twopair
        """
        score = ComboPoints()
        score.dice = [i for i in range(len(input_array))]

        score.type = Payout.ThreePair
        score.apply_points(input_array)
        return score

    @staticmethod
    def create_sum_dice(input_array, exclude_array):
        """create the sum of dice, keep 1s and 5s
           exclude the indexes of input in the exclude array, as the dice are already used.
        """
        score = ComboPoints()

        score.dice = list(filter( \
                    lambda v: v not in exclude_array and \
                    ComboPoints.DICEVALUE[input_array[v]] > 0, \
                    range(len(input_array))))
        score.type = Payout.SumDice
        score.apply_points(input_array)

        return score



class ScoreDice:
    """Compute the score for the given dice
    """
    SIDES = 6

    def __init__(self, rolled):
        # array indicating which dice in rolled were actually used
        self.dice_used = [False for i in rolled]
        # total score
        self.total_points = 0
        # list of individual scores
        self.scores = []
        # the dice that were selected
        self.rolled = rolled

        self.evaluate()
        self.sum_points()


    def sum_points(self):
        """Add up all the points for all the combos
        """
        self.total_points = 0
        for score in self.scores:
            self.total_points += score.points
            #
            # track which dice used in the score.
            for idx in score.dice:
                self.dice_used[idx] = True


    def evaluate(self):
        """Evaluate the dice to see what combos we have
        """
        self.scores = []
        count = len(self.rolled)

        # if we rolled nothing new, we get nothing.
        if count == 0:
            return

        counts = [0 for i in range(ScoreDice.SIDES)]

        for die in self.rolled:
            counts[die-1] += 1

        score = None
        # check for straight
        has_all = count == 6 and not 0 in counts
        if has_all:
            score = ComboPoints.create_straight(input_array=self.rolled)
            self.scores.append(score)
        else:
            #
            # do more checks if not a straight
            #

            # find the OF A KINDs
            matchsize = count
            while matchsize >= 3:
                #
                # find matchsize of a kind
                for i in range(ScoreDice.SIDES):
                    if counts[i] == matchsize:
                        # found one!
                        score = ComboPoints.create_match(self.rolled, i+1)
                        self.scores.append(score)
                matchsize -= 1

            used = []
            for score in self.scores:
                used.extend(score.dice)

            #
            # take any unused dice and check for 1s or 5s
            #
            score = ComboPoints.create_sum_dice(self.rolled, used)
            if score.points > 0:
                self.scores.append(score)

            #
            # check for 3 pair (or 4 plus 2)
            #
            if count == 6:

                # we only check for this AFTER the others because of combinations
                # like 1 1 6 6 6 6, which
                # should be 1400 points, vs 750 points for 3 pair.
                pairs = 0
                for num_dice in counts:
                    if num_dice == 2:
                        pairs += 1
                    elif num_dice == 4:
                        pairs += 2

                if pairs == 3:
                    # we have to decide whether to use this one or the others,
                    # depending on which is worth more points
                    score = ComboPoints.create_three_pairs(self.rolled)
                    countused = sum(len(score.dice) for score in self.scores)
                    total = sum(score.points for score in self.scores)
                    if countused < 6 or total < score.points:
                        # replace our scores list with the 3 pairs. It is better
                        # to use all 6 dice if they are
                        # all selected. But, better to keep original if the score was better
                        self.scores.clear()
                        self.scores.append(score)
