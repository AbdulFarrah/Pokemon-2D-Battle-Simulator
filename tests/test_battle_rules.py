import json
import subprocess
import sys
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
    pygame_stub.MOUSEBUTTONDOWN = 1
    pygame_stub.MOUSEWHEEL = 2
    pygame_stub.event = SimpleNamespace(pump=lambda: None, get=lambda: [])
    pygame_stub.display = SimpleNamespace(flip=lambda: None)
    pygame_stub.time = SimpleNamespace(
        Clock=lambda: SimpleNamespace(tick=lambda *_args: None),
        get_ticks=lambda: 0,
        wait=lambda *_args: None,
    )
    sys.modules["pygame"] = pygame_stub

from src.damage import Damage
from src.game import Game, RuntimeDataError
from src.move import Move
from src.pokemon import Pokemon
from src.online_setup import code_to_invite, copy_to_clipboard, ip_to_code, paste_from_clipboard
from data.image_fetcher import image_filename


def move_data(name, *, category="Physical", power="40", pp="10", move_type="Normal"):
    return {
        "Name": name, "Type": move_type, "Category": category, "Contest": "Cool",
        "PP": pp, "Power": power, "Accuracy": "100",
    }


def pokemon_data(name, *, hp=50, attack=50, defense=50, speed=50):
    return {
        "Name": name, "Types": ["Normal"], "Generation": 1, "hp": hp,
        "attack": attack, "defense": defense, "special_attack": 50,
        "special_defense": 50, "speed": speed, "Moves": [],
    }


class BattleRulesTests(unittest.TestCase):
    def make_game(self):
        game = Game.__new__(Game)
        game.move_log_stack = []
        game.move_hitted_stack = []
        game.draw_battle_message = lambda _duration: None
        game.damage = SimpleNamespace(calculate_damage=lambda *_args: [0, 0])
        return game

    def test_zero_pp_moves_are_excluded_and_available_actions_remain(self):
        game = self.make_game()
        exhausted = SimpleNamespace(pp=0)
        active = SimpleNamespace(moves=[exhausted], hp=100)
        bench = SimpleNamespace(moves=[], hp=30)
        player = SimpleNamespace(current_pokemon=active, pokemons=[active, bench])
        self.assertEqual(game.usable_move_indices(active), [])
        self.assertEqual(game.valid_commands(player), ["switch", "list", "exit"])

    def test_switch_option_remains_visible_without_a_bench_and_returns_safely(self):
        game = self.make_game()
        active = SimpleNamespace(name="Pikachu", moves=[], hp=100)
        player = SimpleNamespace(current_pokemon=active, current_pokemon_index=0,
                                 pokemons=[active])
        self.assertEqual(game.valid_commands(player), ["switch", "list", "exit"])
        self.assertIsNone(game.handle_switch_command(player))

    def test_mouse_wheel_buttons_are_not_treated_as_battle_clicks(self):
        for button in (4, 5):
            event = SimpleNamespace(type=pygame.MOUSEBUTTONDOWN, button=button)
            self.assertFalse(Game.is_primary_mouse_down(event))
        click = SimpleNamespace(type=pygame.MOUSEBUTTONDOWN, button=1)
        self.assertTrue(Game.is_primary_mouse_down(click))
        wheel = SimpleNamespace(type=pygame.MOUSEWHEEL)
        self.assertFalse(Game.is_primary_mouse_down(wheel))

    def test_move_pp_is_clamped(self):
        move = Move(move_data("Tackle", pp="5"))
        move.update_pp(-20)
        self.assertEqual(move.pp, 0)
        move.update_pp(50)
        self.assertEqual(move.pp, move.max_pp)

    def test_transform_copies_moves_and_image_without_copying_stats(self):
        game = self.make_game()
        copied_move = Move(move_data("Tackle", pp="20"))
        copied_move.pp = 2
        transformed = Pokemon([Move(move_data("Transform", category="Status", power="None"))],
                              pokemon_data("Mew", attack=75))
        target = Pokemon([copied_move], pokemon_data("Pikachu", attack=55))
        original_attack = transformed.attack
        game.pokemon_images = {"Mew": "mew-sprite", "Pikachu": "pikachu-sprite"}
        game.apply_transform(transformed, target)
        self.assertEqual(transformed.attack, original_attack)
        self.assertNotEqual(transformed.attack, target.attack)
        self.assertEqual(transformed.moves[0].name, "Tackle")
        self.assertEqual(transformed.moves[0].pp, transformed.moves[0].max_pp)
        self.assertIsNot(transformed.moves[0], copied_move)
        self.assertEqual(transformed.transformed_image, "pikachu-sprite")

        transformed.update_hp(-transformed.hp)
        self.assertTrue(game.check_fainting(transformed))
        self.assertEqual([move.name for move in transformed.moves], ["Transform"])
        self.assertIsNone(transformed.transformed_image)

    def test_transform_state_survives_switching_out_and_back(self):
        game = self.make_game()
        transformed = Pokemon([Move(move_data("Transform", category="Status", power="None"))],
                              pokemon_data("Mew"))
        target = Pokemon([Move(move_data("Tackle"))], pokemon_data("Pikachu"))
        game.pokemon_images = {"Mew": "mew", "Pikachu": "pikachu"}
        game.apply_transform(transformed, target)
        player = SimpleNamespace(name="Player", pokemons=[transformed, Pokemon([], pokemon_data("Ditto"))],
                                 current_pokemon=transformed, current_pokemon_index=0)
        game.player1 = player
        game.player2 = SimpleNamespace()
        game.draw_battle_message = lambda *_args: None
        game.switch(player, 1)
        game.switch(player, 0)
        self.assertEqual(transformed.moves[0].name, "Tackle")
        self.assertEqual(game.get_pokemon_image(transformed), "pikachu")

    def test_sketch_uses_latest_observed_move_and_keeps_failed_sketch(self):
        game = self.make_game()
        sketch = Move(move_data("Sketch", category="Status", power="None"))
        user = Pokemon([sketch], pokemon_data("Smeargle"))
        opponent_move = Move(move_data("Tackle", pp="20"))
        opponent = Pokemon([opponent_move], pokemon_data("Pikachu"))
        player = SimpleNamespace(name="Player")

        game.fight(sketch, user, opponent, player, 1)
        self.assertEqual(user.moves[0].name, "Sketch")

        game.fight(opponent_move, opponent, user, SimpleNamespace(name="Rival"), 1)
        game.fight(user.moves[0], user, opponent, player, 1)
        copied = user.moves[0]
        self.assertEqual(copied.name, "Tackle")
        self.assertEqual(copied.pp, copied.max_pp)
        self.assertIsNot(copied, opponent_move)

    def test_status_moves_without_power_are_excluded_except_implemented_effects(self):
        game = self.make_game()
        game.move_size = 10
        game.moves = [
            move_data("Splash", category="Status", power="None"),
            move_data("Recover", category="Status", power="None"),
            move_data("Transform", category="Status", power="None"),
            move_data("Sketch", category="Status", power="None"),
            move_data("Tackle"),
        ]
        generated = game.generate_random_moves([move["Name"] for move in game.moves])
        names = {move.name for move in generated}
        self.assertNotIn("Splash", names)
        self.assertTrue({"Recover", "Transform", "Sketch", "Tackle"}.issubset(names))

    def test_fixed_damage_moves_still_obey_immunity_and_retain_recoil(self):
        damage = Damage()
        attacker = SimpleNamespace(lv=50, attack=50, defense=50, sp_attack=50,
                                   sp_defense=50, types=["Normal"])
        ghost = SimpleNamespace(lv=50, attack=50, defense=50, sp_attack=50,
                                sp_defense=50, types=["Ghost"])
        normal = SimpleNamespace(lv=50, attack=50, defense=50, sp_attack=50,
                                 sp_defense=50, types=["Normal"])
        hyper_beam = Move(move_data("Hyper Beam", category="Special", power="150"))
        explosion = Move(move_data("Explosion", power="250"))
        self_destruct = Move(move_data("Self-Destruct", power="200"))
        self.assertEqual(damage.calculate_damage(hyper_beam, attacker, ghost), [0, 0])
        self.assertEqual(damage.calculate_damage(hyper_beam, attacker, normal), [150, 0])
        self.assertEqual(damage.calculate_damage(explosion, attacker, ghost), [0, 500])
        self.assertEqual(damage.calculate_damage(self_destruct, attacker, ghost), [0, 500])

    def test_fainted_pokemon_cannot_be_healed(self):
        pokemon = Pokemon([], pokemon_data("Test"))
        pokemon.update_hp(-pokemon.hp)
        self.assertTrue(pokemon.fainted)
        self.assertEqual(pokemon.update_hp(50), 0)
        self.assertEqual(pokemon.hp, 0)


class StartupAndInviteTests(unittest.TestCase):
    def test_runtime_schema_rejects_missing_move_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pokemon.json").write_text(json.dumps({"pokemons": [pokemon_data("Pikachu")]}))
            (root / "data.json").write_text(json.dumps({"moves": [{"Name": "Bad"}]}))
            resolver = lambda relative: root / Path(relative).name
            with patch.object(Game, "resource_path", side_effect=resolver):
                with self.assertRaises(RuntimeDataError):
                    Game.load_runtime_data()

    def test_invite_code_contains_ipv4_and_a_random_secret(self):
        code = ip_to_code("192.0.2.10")
        ip, token = code_to_invite(code)
        self.assertEqual(ip, "192.0.2.10")
        self.assertEqual(len(token), 16)
        self.assertNotEqual(code, ip_to_code("192.0.2.10"))

    def test_invite_code_can_be_copied_and_pasted(self):
        clipboard = {"value": None}
        scrap = SimpleNamespace(
            SCRAP_TEXT="text/plain",
            init=lambda: None,
            put=lambda _kind, value: clipboard.update(value=value),
            get=lambda _kind: clipboard["value"],
        )
        with patch.object(pygame, "scrap", scrap, create=True):
            self.assertTrue(copy_to_clipboard("invite-code"))
            self.assertEqual(paste_from_clipboard(), "invite-code")

    def test_clipboard_failure_does_not_crash_setup(self):
        scrap = SimpleNamespace(init=lambda: (_ for _ in ()).throw(RuntimeError("unavailable")))
        with (patch.object(pygame, "scrap", scrap, create=True),
              patch("src.online_setup.shutil.which", return_value=None)):
            self.assertFalse(copy_to_clipboard("invite-code"))
            self.assertEqual(paste_from_clipboard(), "")

    def test_copy_falls_back_to_windows_clip_from_wsl(self):
        scrap = SimpleNamespace(init=lambda: None,
                                put=lambda *_args: (_ for _ in ()).throw(RuntimeError("Wayland")))
        with (patch.object(pygame, "scrap", scrap, create=True),
              patch("src.online_setup.shutil.which", return_value="/mnt/c/Windows/clip.exe"),
              patch("src.online_setup.subprocess.run") as run):
            self.assertTrue(copy_to_clipboard("invite-code"))
        self.assertEqual(run.call_args.kwargs["input"], b"invite-code")

    def test_paste_falls_back_to_powershell_from_wsl(self):
        scrap = SimpleNamespace(init=lambda: None, get=lambda _kind: None)
        result = subprocess.CompletedProcess([], 0, stdout=b"invite-code\r\n")
        with (patch.object(pygame, "scrap", scrap, create=True),
              patch("src.online_setup.shutil.which", side_effect=(None, "/mnt/c/Windows/powershell.exe")),
              patch("src.online_setup.subprocess.run", return_value=result)):
            self.assertEqual(paste_from_clipboard(), "invite-code")

    def test_windows_unsafe_image_characters_are_sanitized(self):
        self.assertEqual(image_filename("Type: Null"), "Type__Null.png")


if __name__ == "__main__":
    unittest.main()
