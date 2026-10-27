import math
from src.type import Type # type: ignore

class Damage:
    special_moves = ["Blast Burn", "Eternabeam", "Frenzy Plant", "Giga Impact", "Hydro Cannon","Hyper Beam", "Meteor Assault", "Prismatic Laser", "Roar of Time","Rock Wrecker", "Shadow Half"]
    recoil_moves = ["Brave Bird", "Double-Edge", "Flare Blitz", "Head Charge", "Head Smash","Light of Ruin", "Self-Destruct", "Shadow End", "Shadow Rush", "Struggle","Submission", "Take Down", "Volt Tackle", "Wave Crash", "Wild Charge", "Wood Hammer"]
    def __init__(self):
        pass

    def calculate_modifier(self, stab, type_eff):
        return (0.93) * (1.75 if stab == True else 1.0) * type_eff

    def calculate_damage(self, move, pokemon1, pokemon2):
        # NOTE: ignore Status move for now
        main,recoil =0,0
        if move.category == 'Status':
            return [0,0]
        if move.name in self.special_moves:
            if Type().get_effectiveness(move.type, pokemon2.types) == 0:
                return [0, 0]
            return [150,0]
        if move.category == 'Physical':
            numerator = (((2 * pokemon1.lv) / 5) + 2) * move.power * (pokemon1.attack/pokemon2.defense)
        elif move.category == 'Special':
            numerator = (((2 * pokemon1.lv) / 5) + 2) * move.power * (pokemon1.sp_attack/pokemon2.sp_defense)
        if move.type in pokemon1.types:
            stab = True
        else:
            stab = False
        modifier = self.calculate_modifier(stab, Type().get_effectiveness(move.type, pokemon2.types))
        main = math.floor( ((numerator / 50) + 2) * modifier )
        if move.name in self.recoil_moves:
            recoil = main // 4
        if move.name == 'Explosion':
            recoil = 500
            main = 500
        if move.name == 'Self-Destruct' or move.name == 'Selfdestruct':
            recoil = 500
            main = 180
        if (move.name in ('Explosion', 'Self-Destruct', 'Selfdestruct')
                and Type().get_effectiveness(move.type, pokemon2.types) == 0):
            main = 0
        return [main,recoil]
