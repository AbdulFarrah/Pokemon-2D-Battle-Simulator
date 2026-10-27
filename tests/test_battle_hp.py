import sys
import types
import unittest
from types import SimpleNamespace

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
from src.pokemon import Pokemon


def make_pokemon(name):
    return Pokemon([], {
        "Name": name,
        "Types": ["Normal"],
        "hp": 50,
        "attack": 50,
        "defense": 50,
        "special_attack": 50,
        "special_defense": 50,
        "speed": 50,
    })


class BattleHPTests(unittest.TestCase):
    def setUp(self):
        self.game = Game.__new__(Game)
        self.game.heal_user_moves = ["Recover"]
        self.game.heal_target_moves = ["Heal Pulse"]
        self.game.drain_moves = ["Drain Punch"]
        self.game.move_log_stack = []
        self.game.move_hitted_stack = []
        self.game.draw_battle_message = lambda _duration: None
        self.game.damage = SimpleNamespace(calculate_damage=lambda *_args: [50, 0])

        self.user = make_pokemon("User")
        self.target = make_pokemon("Target")
        self.player = SimpleNamespace(name="Player")

    def use_move(self, name, user=None, target=None):
        move = SimpleNamespace(
            name=name,
            accuracy=100,
            update_pp=lambda _delta: None,
        )
        self.game.fight(move, user or self.user, target or self.target, self.player, 1)

    def test_hp_updates_are_clamped_and_report_actual_change(self):
        self.assertEqual(self.user.update_hp(10_000), 0)
        self.assertEqual(self.user.hp, self.user.max_hp)
        self.assertEqual(self.user.update_hp(-10_000), -self.user.max_hp)
        self.assertEqual(self.user.hp, 0)

    def test_self_healing_is_half_max_hp_and_capped(self):
        self.user.update_hp(-20)
        self.use_move("Recover")
        self.assertEqual(self.user.hp, min(self.user.max_hp, self.user.max_hp - 20 + self.user.max_hp // 2))
        self.user.hp = self.user.max_hp - 1
        self.use_move("Recover")
        self.assertEqual(self.user.hp, self.user.max_hp)

    def test_target_healing_is_half_target_max_hp_and_capped(self):
        self.target.update_hp(-20)
        self.use_move("Heal Pulse")
        self.assertEqual(self.target.hp, min(self.target.max_hp, self.target.max_hp - 20 + self.target.max_hp // 2))
        self.target.hp = self.target.max_hp - 1
        self.use_move("Heal Pulse")
        self.assertEqual(self.target.hp, self.target.max_hp)

    def test_drain_heals_only_hp_removed_from_target(self):
        self.target.hp = 10
        self.user.update_hp(-5)
        self.use_move("Drain Punch")
        self.assertEqual(self.target.hp, 0)
        self.assertEqual(self.user.hp, min(self.user.max_hp, self.user.max_hp - 5 + 10))


if __name__ == "__main__":
    unittest.main()
