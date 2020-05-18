"""This lambda function is for generating rolls for a farkle game online

"""
import json
import decimal
import boto3
from botocore.exceptions import ClientError
import gamestate
import player


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


def update_table(db_conn, table_name, key_dict, update_dict):
    """Update the table based on list of updates. All updates must be numeric additions to the
       current value. Must be negative to subtract
    """
    if update_dict is not None and len(update_dict) > 0:
        updates = []
        variables = {}
        idx = 1
        haszero = False
        for key, value in update_dict.items():
            if isinstance(value, str):
                updates.append(key + " = :a" + str(idx))
            else:
                updates.append(key + " = if_not_exists(" + key + ",:zero) + :a" + str(idx))
                haszero = True
            variables[':a' + str(idx)] = value
            idx += 1
        if haszero:
            variables[':zero'] = 0
        update_string = "set " + ', '.join(updates)
        table = db_conn.Table(table_name)
        table.update_item(
            Key=key_dict,
            UpdateExpression=update_string,
            ExpressionAttributeValues=variables,
            ReturnValues="UPDATED_NEW"
        )

def update_gamestate(db_conn, game_state):
    """save the game state to the dynamo db
    """
    print(game_state)
    table = db_conn.Table('sessions')
    save_state = game_state.get_save_dict()
    table.put_item(Item=save_state)
    update_table(db_conn, 'players', {'player_id': game_state.player_id}, \
        game_state.player_adjustments)
    update_table(db_conn, 'games', {'gamename': 'farkle'}, game_state.game_adjust)


def load_game(db_conn):
    """load game from db
    """
    table = db_conn.Table('games')
    response = table.get_item(
        Key={
            'gamename': 'farkle'
        }
    )
    return response['Item']

def load_player(db_conn, player_id):
    """load player data from db
    """
    table = db_conn.Table('players')
    response = table.get_item(
        Key={
            'player_id': player_id
        }
    )
    item = response['Item']
    player_1 = player.Player()
    player_1.init_dict(item)
    return player_1

def load_gamestate(db_conn, session):
    """get the game state from the db
    """
    try:
        table = db_conn.Table('sessions')
        response = table.get_item(
            Key={
                'uniqID': session
            }
        )
        player_1 = load_player(db_conn, response['Item']['player_id'])
        game_data = load_game(db_conn)
    except ClientError:
        game_state = gamestate.GameState()
        game_state.uniqID = session
        game_state.message = "Unknown game state"
        return game_state
    else:
        item = response['Item']
        game_state: gamestate.GameState = json.loads(json.dumps(item, cls=GameEncoder)\
            , object_hook=object_decoder)
        game_state.update_from_player(player_1)
        game_state.update_from_game(game_data)
        return game_state


def buyboost_handler(data):
    """handle boost buying
    """
    db_conn = get_dynamo()

    # set our defaults
    if 'gems' in data:
        game_state = load_gamestate(db_conn, data['session'])
        if game_state.buy_boosts(int(data['gems'])):
            update_gamestate(db_conn, game_state)

        return format_response(game_state)
    else:
        return format_response(None, None, 502)

def roll_handler(data):
    """Handle the next roll from client. Should pass the dice held
        and whether it is using the extra roll power up
        in the body
    """
    db_conn = get_dynamo()
    # set our defaults
    if 'hold' not in data:
        data['hold'] = None
    if 'extra' not in data:
        data['extra'] = False
    if 'session' not in data:
        return format_response({'message': 'no session specified'}, None, 502)

    game_state = load_gamestate(db_conn, data['session'])
    if game_state.roll(data['hold'], data['extra']):
        update_gamestate(db_conn, game_state)

    return format_response(game_state)

def unfarkle_handler(data):
    """unfarkle
    """
    db_conn = get_dynamo()

    if 'session' not in data:
        return format_response({'message': 'no session specified'}, None, 502)

    game_state = load_gamestate(db_conn, data['session'])
    if game_state.unfarkle():
        update_gamestate(db_conn, game_state)

    return format_response(game_state)


def stop_handler(data):
    """End a turn. Go to the next turn or end the game.
    """
    db_conn = get_dynamo()

    # set our defaults
    if 'hold' not in data:
        data['hold'] = None
    if 'double' not in data:
        data['double'] = False
    if 'session' not in data:
        return format_response({'message': 'no session specified'}, None, 502)


    game_state = load_gamestate(db_conn, data['session'])
    if game_state.end_turn(data['hold'], data['double']):
        update_gamestate(db_conn, game_state)

    return format_response(game_state)


def start_handler(data):
    """ start a new turn on farkle. requires the following post parameters:
        bet - number of credits to wager
        mode - LONG, NORMAL or TUTORIAL
        player_id - uuid of the player
        login_key - validation key for the player
        session - if continuing existing game, include session. can also start a
         new game with previous session
    """
    # set our defaults
    if 'bet' not in data:
        data['bet'] = 500
    if 'mode' not in data:
        data['mode'] = 'NORMAL'
    if 'session' not in data:
        data['session'] = ''
    if 'player_id' not in data:
        data['player_id'] = ''

    try:
        db_conn = get_dynamo()

        data['player_id'] = str(data['player_id'])
        if len(str(data['session'])) > 15:
            game_state = load_gamestate(db_conn, data['session'])
            if str(game_state.player_id) != data['player_id']:
                game_state.message = "wrong player id"
                return format_response(game_state, None, 502)
        else:
            game_state = gamestate.GameState()
            # create new player if play_id not set
            if data['player_id'] == '':
                player_1 = player.Player()
            else:
                player_1 = load_player(db_conn, data['player_id'])
            game_state.gameMode = data['mode']
            game_state.update_from_player(player_1)

        game_state.start_turn(int(data['bet']))
        update_gamestate(db_conn, game_state)

        return format_response(game_state)
    except Exception as exception:
        return format_response({'message': str(exception)})


def shared_handler(event, context):
    """handle multiple functions based on path
    """
    command = event['pathParameters']['command']
    data = {}
    if 'body' in event:
        body = event['body']
        if body.startswith('{'):
            data = json.loads(body)
        else:
            data = {}

    if command == 'start':
        return start_handler(data)
    elif command == 'roll':
        return roll_handler(data)
    elif command == 'stop':
        return stop_handler(data)
    elif command == 'unfarkle':
        return unfarkle_handler(data)
    elif command == 'buyboosts':
        return buyboost_handler(data)
    else:
        return format_response({'message': 'unknown command'}, None, 502)
