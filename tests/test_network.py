import builtins
import json
import pickle
import sys
import struct
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

try:
    import pygame  # noqa: F401
except ModuleNotFoundError:
    pygame_stub = types.ModuleType("pygame")
    pygame_stub.QUIT = -1
    pygame_stub.event = SimpleNamespace(pump=lambda: None, get=lambda: [])
    pygame_stub.display = SimpleNamespace(flip=lambda: None)
    pygame_stub.time = SimpleNamespace(
        Clock=lambda: SimpleNamespace(tick=lambda *_args: None),
        get_ticks=lambda: 0,
        wait=lambda *_args: None,
    )
    sys.modules["pygame"] = pygame_stub

from src.game import Game
from src.network import MAX_MESSAGE_SIZE, ProtocolError, receive_message, send_message
from src.base import get_online_role_from_click


class MemorySocket:
    def __init__(self, data=b"", chunk_size=None):
        self.data = bytearray(data)
        self.chunk_size = chunk_size

    def sendall(self, data):
        self.data.extend(data)

    def recv(self, size):
        if not self.data:
            return b""
        count = min(size, self.chunk_size or size)
        result = bytes(self.data[:count])
        del self.data[:count]
        return result


class NetworkProtocolTests(unittest.TestCase):
    def test_round_trip_and_multiple_messages(self):
        writer = MemorySocket()
        send_message(writer, {"type": "move", "accuracy": 47})
        send_message(writer, {"type": "switch", "switch_index": 2})

        reader = MemorySocket(writer.data, chunk_size=3)
        self.assertEqual(receive_message(reader), {"type": "move", "accuracy": 47})
        self.assertEqual(receive_message(reader), {"type": "switch", "switch_index": 2})

    def test_fragmented_header_and_payload_are_read_completely(self):
        payload = json.dumps({"version": 1, "type": "team", "name": "Player"}).encode("utf-8")
        framed = struct.pack("!I", len(payload)) + payload
        self.assertEqual(receive_message(MemorySocket(framed, chunk_size=1)),
                         {"type": "team", "name": "Player"})

    def test_rejects_zero_and_oversized_lengths(self):
        for size in (0, MAX_MESSAGE_SIZE + 1):
            with self.subTest(size=size):
                with self.assertRaises(ProtocolError):
                    receive_message(MemorySocket(struct.pack("!I", size)))

    def test_rejects_invalid_json_and_non_object_json(self):
        for payload in (b"{", b"[]"):
            with self.subTest(payload=payload):
                framed = struct.pack("!I", len(payload)) + payload
                with self.assertRaises(ProtocolError):
                    receive_message(MemorySocket(framed))

    def test_rejects_pickle_without_executing_its_reduce_payload(self):
        class MaliciousPayload:
            def __reduce__(self):
                command = f"open({str(marker)!r}, 'w').write('executed')"
                return builtins.exec, (command,)

        with tempfile.TemporaryDirectory() as temp_dir:
            marker = Path(temp_dir) / "pickle-executed"
            payload = pickle.dumps(MaliciousPayload())
            framed = struct.pack("!I", len(payload)) + payload
            with self.assertRaises(ProtocolError):
                receive_message(MemorySocket(framed))
            self.assertFalse(marker.exists())

    def test_send_rejects_non_json_values(self):
        with self.assertRaises(ProtocolError):
            send_message(MemorySocket(), {"bad": object()})

    def test_rejects_missing_or_unknown_protocol_version(self):
        for message in ({"type": "move"}, {"version": 9, "type": "move"}):
            with self.subTest(message=message):
                payload = json.dumps(message).encode("utf-8")
                framed = struct.pack("!I", len(payload)) + payload
                with self.assertRaises(ProtocolError):
                    receive_message(MemorySocket(framed))


class GameMessageValidationTests(unittest.TestCase):
    def setUp(self):
        self.game = Game.__new__(Game)
        self.game.pokemons = [{
            "Name": "Pikachu",
            "Moves": ["Thunderbolt"],
            "Types": ["Electric"],
            "hp": 35,
            "attack": 55,
            "defense": 40,
            "special_attack": 50,
            "special_defense": 50,
            "speed": 90,
        }]
        self.game.moves = [{
            "Name": "Thunderbolt",
            "Type": "Electric",
            "Category": "Special",
            "Contest": "Cool",
            "PP": "15",
            "Power": "90",
            "Accuracy": "100",
        }]

    def test_team_message_rebuilds_local_objects_from_names(self):
        name, team, size = self.game._decode_opponent_team({
            "type": "team",
            "name": "Rival",
            "battle_size": 1,
            "team": [{"name": "Pikachu", "moves": ["Thunderbolt"]}],
        })
        self.assertEqual((name, size), ("Rival", 1))
        self.assertEqual(team[0].name, "Pikachu")
        self.assertEqual(team[0].moves[0].name, "Thunderbolt")

    def test_team_message_rejects_unknown_or_unlearnable_moves(self):
        bad_team = [{"name": "Pikachu", "moves": ["Unknown Move"]}]
        with self.assertRaises(ProtocolError):
            self.game._decode_opponent_team({
                "type": "team", "name": "Rival", "battle_size": 1, "team": bad_team,
            })

    def test_fight_message_rejects_invalid_move_index(self):
        active = SimpleNamespace(name="Pikachu", moves=[SimpleNamespace(name="Thunderbolt")])
        self.game.player2 = SimpleNamespace(current_pokemon=active, pokemons=[active])
        wire = MemorySocket()
        send_message(wire, {
            "type": "move",
            "action": {"kind": "fight", "pokemon": "Pikachu", "move_index": 4},
            "accuracy": 50,
        })
        self.game.conn = MemorySocket(wire.data)
        with self.assertRaises(ProtocolError):
            self.game.receive_opponent_move()

    def test_switch_message_rejects_fainted_target(self):
        active = SimpleNamespace(name="Pikachu", hp=20)
        fainted = SimpleNamespace(name="Raichu", hp=0)
        self.game.player2 = SimpleNamespace(
            current_pokemon=active,
            current_pokemon_index=0,
            pokemons=[active, fainted],
        )
        wire = MemorySocket()
        send_message(wire, {"type": "switch", "switch_index": 1})
        self.game.conn = MemorySocket(wire.data)
        with self.assertRaises(ProtocolError):
            self.game.recv_switch_message()

    def test_forfeit_records_loser_and_winner_and_ends_match(self):
        self.game.player1 = SimpleNamespace(name="Player One")
        self.game.player2 = SimpleNamespace(name="Player Two")
        self.game.gameOver = False
        displayed = []
        self.game.display_blackout_message = displayed.append

        self.game.finish_forfeit(self.game.player2)

        self.assertEqual(self.game.forfeit_by, "Player Two")
        self.assertTrue(self.game.gameOver)
        self.assertEqual(displayed, [[
            "Player Two forfeited the match...",
            "Player One wins!",
        ]])

    def test_player_two_forfeit_stops_first_turn_before_action_resolution(self):
        player_one_move = SimpleNamespace(name="Thunderbolt", pp=10, max_pp=10)
        player_two_move = SimpleNamespace(name="Tackle", pp=10, max_pp=10)
        player_one_pokemon = SimpleNamespace(name="Pikachu", moves=[player_one_move])
        player_two_pokemon = SimpleNamespace(name="Eevee", moves=[player_two_move])
        self.game.player1 = SimpleNamespace(
            name="Player One", current_pokemon=player_one_pokemon, pokemons=[player_one_pokemon],
        )
        self.game.player2 = SimpleNamespace(
            name="Player Two", current_pokemon=player_two_pokemon, pokemons=[player_two_pokemon],
        )
        self.game.game_mode = "2"
        self.game.gameOver = False
        self.game.forfeit_by = None
        self.game.screen = SimpleNamespace(fill=lambda *_: None)
        self.game.draw_top_info = lambda *_: None
        self.game.draw_middle_area = lambda *_: None
        self.game.draw_battle_message = lambda *_: None
        self.game.draw_bottom_buttons = lambda *_: None
        self.game.get_button_click = lambda *_: "fight"
        self.game.handle_fight_command = lambda player: ("fight", player.current_pokemon, 0)
        self.game.prompt_player_command = lambda *_: "exit"
        self.game.display_blackout_message = lambda *_: None

        with patch("src.game.pygame.event.get", return_value=[SimpleNamespace(type=0)]), \
             patch("src.game.pygame.display.flip", return_value=None):
            self.game.game_loop()

        self.assertTrue(self.game.gameOver)
        self.assertEqual(self.game.forfeit_by, "Player Two")

    def test_player_one_forfeit_ends_local_pvp_match(self):
        p1_pokemon = SimpleNamespace(name="Pikachu", types=[], moves=[])
        p2_pokemon = SimpleNamespace(name="Eevee", types=[], moves=[])
        self.game.player1 = SimpleNamespace(
            name="Player One", current_pokemon=p1_pokemon, pokemons=[p1_pokemon],
        )
        self.game.player2 = SimpleNamespace(
            name="Player Two", current_pokemon=p2_pokemon, pokemons=[p2_pokemon],
        )
        self.game.game_mode = "2"
        self.game.gameOver = False
        self.game.forfeit_by = None
        self.game.screen = SimpleNamespace(fill=lambda *_: None)
        self.game.draw_top_info = lambda *_: None
        self.game.draw_middle_area = lambda *_: None
        self.game.draw_battle_message = lambda *_: None
        self.game.draw_bottom_buttons = lambda *_: None
        self.game.get_button_click = lambda *_: "exit"
        self.game.display_blackout_message = lambda *_: None

        with patch("src.game.pygame.event.get", return_value=[SimpleNamespace(type=0)]), \
             patch("src.game.pygame.display.flip", return_value=None):
            self.game.game_loop()

        self.assertTrue(self.game.gameOver)
        self.assertEqual(self.game.forfeit_by, "Player One")

    def test_host_synchronizes_random_speed_tie_winner(self):
        host_pokemon = SimpleNamespace(speed=80)
        client_pokemon = SimpleNamespace(speed=80)
        self.game.settings = {"is_host": True}
        self.game.player1 = SimpleNamespace(current_pokemon=host_pokemon)
        self.game.player2 = SimpleNamespace(current_pokemon=client_pokemon)
        self.game.conn = MemorySocket()
        action1 = ("fight", host_pokemon, 0)
        action2 = ("fight", client_pokemon, 0)

        with patch("src.game.random.choice", return_value="client"):
            winner = self.game.sync_online_speed_tie(action1, action2)

        self.assertEqual(winner, "client")
        self.assertEqual((host_pokemon.speed, client_pokemon.speed), (80, 90))
        self.assertEqual(receive_message(self.game.conn), {
            "type": "turn_sync", "speed_tie_winner": "client",
        })

    def test_client_applies_host_synchronized_speed_tie_result(self):
        client_pokemon = SimpleNamespace(speed=80)
        host_pokemon = SimpleNamespace(speed=80)
        self.game.settings = {"is_host": False}
        self.game.player1 = SimpleNamespace(current_pokemon=client_pokemon)
        self.game.player2 = SimpleNamespace(current_pokemon=host_pokemon)
        wire = MemorySocket()
        send_message(wire, {"type": "turn_sync", "speed_tie_winner": "host"})
        self.game.conn = MemorySocket(wire.data)

        winner = self.game.sync_online_speed_tie(
            ("fight", client_pokemon, 0), ("fight", host_pokemon, 0),
        )

        self.assertEqual(winner, "host")
        self.assertEqual((client_pokemon.speed, host_pokemon.speed), (80, 90))

    def test_host_sends_no_winner_when_speeds_differ(self):
        host_pokemon = SimpleNamespace(speed=90)
        client_pokemon = SimpleNamespace(speed=80)
        self.game.settings = {"is_host": True}
        self.game.player1 = SimpleNamespace(current_pokemon=host_pokemon)
        self.game.player2 = SimpleNamespace(current_pokemon=client_pokemon)
        self.game.conn = MemorySocket()

        winner = self.game.sync_online_speed_tie(
            ("fight", host_pokemon, 0), ("fight", client_pokemon, 0),
        )

        self.assertIsNone(winner)
        self.assertEqual((host_pokemon.speed, client_pokemon.speed), (90, 80))
        self.assertEqual(receive_message(self.game.conn), {
            "type": "turn_sync", "speed_tie_winner": None,
        })


class OnlineSetupChoiceTests(unittest.TestCase):
    def test_only_host_or_join_button_clicks_choose_a_role(self):
        class Button:
            def __init__(self, position):
                self.position = position

            def is_clicked(self, position):
                return position == self.position

        host_button = Button((10, 10))
        join_button = Button((20, 20))
        self.assertIs(get_online_role_from_click((10, 10), host_button, join_button), True)
        self.assertIs(get_online_role_from_click((20, 20), host_button, join_button), False)
        self.assertIsNone(get_online_role_from_click((30, 30), host_button, join_button))


if __name__ == "__main__":
    unittest.main()
