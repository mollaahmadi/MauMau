import os
import redis
from threading import Thread
import json
from player import Player
from random import randint
from time import sleep
from deck import Deck


class WaitForMessage(Thread):
    def __init__(self):
        super(WaitForMessage, self).__init__()
        self.active = True
        self.waiting = True
        self.known_player = None

    def run(self):
        REDIS_URL = os.environ.get('OPENREDIS_URL', 'redis://localhost:6379')
        client = redis.from_url(REDIS_URL)
        pubsub = client.pubsub()
        pubsub.subscribe(['table'])

        for message in pubsub.listen():
            if self.active:
                print('WaitFor: {}'.format(message))
                if message['type'] == 'message':
                    data = json.loads(message['data'])
                    if data['action'] == 'quit':
                        continue
                    if 'player' in data:
                        self.known_player = data['player']
                        self.waiting = False
                        break
            else:
                break
        print('WaitFor exit')


class Interface(object):
    def output_device(self, message):
        raise NotImplemented

    def input_device(self):
        raise NotImplemented


def start(interface):
    REDIS_URL = os.environ.get('OPENREDIS_URL', 'redis://localhost:6379')
    client = redis.from_url(REDIS_URL)

    player = Player(
        'human{}'.format(randint(0, 1000)),
        output_device=interface.output_device,
        input_device=interface.input_device)
    interface.player = player

    wait_for_message = WaitForMessage()
    wait_for_message.start()
    for _ in range(3):
        if not wait_for_message.waiting:
            break
        sleep(1)

    wait_for_message.active = False

    next_step(player,
              client,
              wait_for_message.waiting,
              wait_for_message.known_player)


def next_step(player, client, waiting, known_player):
    if waiting:
        player.next_player = player.name
        player.start()
        sleep(1)
        client.publish(
            'table',
            json.dumps({
                'action': 'other',
                'middle': Deck.get_random_card(),
                'next': player.name}))
    else:
        player.next_player = known_player
        client.publish(
            'table',
            json.dumps({
                'action': 'join',
                'player': player.name,
                'before': known_player}))
        player.start()

    loop(player, client)


def loop(player, client):
    try:
        while True:
            if player.won:
                break
            sleep(5)
    except KeyboardInterrupt:
        client.publish(
            'table',
            json.dumps({
                'action': 'quit',
                'player': player.name,
                'next': player.next_player}))
