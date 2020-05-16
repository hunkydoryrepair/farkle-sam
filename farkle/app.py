"""This lambda function is for generating rolls for a farkle game online

"""
import json
import decimal
import boto3
from botocore.exceptions import ClientError
import gamestate


# import requests

class GameEncoder(json.JSONEncoder):
    """Encode numbers as int if it has no remainder part, otherwise float
    """
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            if o % 1 > 0:
                return float(o)
            else:
                return int(o)
        elif isinstance(o, gamestate.TurnState) or \
             isinstance(o, gamestate.GameState) or \
             isinstance(o, Exception):
            return o.__dict__
        return super(GameEncoder, self).default(o)



def object_decoder(dct):
    """evaluate our dictionary and create the correct type of object
       then initialize that object with the dictionary
    """
    if 'uniqID' in dct:
        gs_temp = gamestate.GameState()
        gs_temp.init_dict(dct)
        return gs_temp
    elif 'diceRolled' in dct:
        ts_temp = gamestate.TurnState()
        ts_temp.init_dict(dct)
        return ts_temp

    return dct



def format_response(obj, headers=None, code=200):
    """format the object to return to client as an object to return from API method,
       which includes statusCode and headers.
    """
    if headers is None:
        headers = {
            "Access-Control-Allow-Origin": "*"
        }
    return {
        "statusCode": code,
        "headers": headers,
        "body": json.dumps(obj, cls=GameEncoder)
    }


def get_dynamo():
    """get the dynamodb data connection
    """
    return boto3.resource('dynamodb', region_name='us-west-1')


def update_gamestate(table, game_state):
    """save the game state to the dynamo db
    """
    item = json.loads(json.dumps(game_state, cls=GameEncoder))
    table.put_item(Item=item)

def load_player(table, player_id):
    response = table.get_item(
        Key={
            'player_id':
        }
    )

def load_gamestate(table, session):
    """get the game state from the db
    """
    try:
        response = table.get_item(
            Key={
                'uniqID': session
            }
        )
    except ClientError as exception:
        game_state = gamestate.GameState()
        game_state.uniqID = session
        return game_state
    else:
        item = response['Item']
        game_state = json.loads(json.dumps(item, cls=GameEncoder), object_hook=object_decoder)
        game_state.message = None
        return game_state


def roll_handler(event, context):
    """Handle the next roll from client. Should pass the dice held
        and whether it is using the extra roll power up
        in the body
    """
    db_conn = get_dynamo()
    table = db_conn.Table('sessions')

    session = event['pathParameters']['session']
    body = event['body']
    if body.startswith('{'):
        data = json.loads(body)
    else:
        data = {}
    # set our defaults
    if 'hold' not in data:
        data['hold'] = None
    if 'extra' not in data:
        data['extra'] = False

    game_state = load_gamestate(table, session)
    if game_state.roll(data['hold'], data['extra']):
        update_gamestate(table, game_state)

    return format_response(game_state)

def unfarkle_handler(event, context):
    """unfarkle
    """
    db_conn = get_dynamo()
    table = db_conn.Table('sessions')

    session = event['pathParameters']['session']

    game_state = load_gamestate(table, session)
    if game_state.unfarkle():
        update_gamestate(table, game_state)

    return format_response(game_state)


def stop_handler(event, context):
    """End a turn. Go to the next turn or end the game.
    """
    db_conn = get_dynamo()
    table = db_conn.Table('sessions')

    session = event['pathParameters']['session']
    body = event['body']
    if body.startswith('{'):
        data = json.loads(body)
    else:
        data = {}
    # set our defaults
    if 'hold' not in data:
        data['hold'] = None
    if 'double' not in data:
        data['double'] = False

    game_state = load_gamestate(table, session)
    if game_state.end_turn(data['hold'], data['double']):
        update_gamestate(table, game_state)

    return format_response(game_state)


def start_handler(event, context):
    """ start a new turn on farkle. requires the following post parameters:
        bet - number of credits to wager
        mode - LONG, NORMAL or TUTORIAL
        player_id - uuid of the player
        login_key - validation key for the player 
        session - if continuing existing game, include session. can also start a new game with previous session
    """

    body = event['body']
    if body.startswith('{'):
        data = json.loads(body)
    else:
        data = {}
    # set our defaults
    if 'bet' not in data:
        data['bet'] = 500
    if 'mode' not in data:
        data['mode'] = 'NORMAL'
    if 'session' not in data:
        data['session'] = ''

    db_conn = get_dynamo()
    table = db_conn.Table('sessions')
    game_state = gamestate.GameState()
    if len(str(data['session'])) > 15:
        load_gamestate(table, session)
    else:
        game_state.player_id = data['player_id']

    game_state.gameMode = mode
    game_state.start_turn(int(bet))

    update_gamestate(table, game_state)

    return format_response(game_state)
