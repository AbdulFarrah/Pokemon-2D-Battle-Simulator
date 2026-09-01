import math

class Pokemon:
    def __init__(self, moves, json_data, lv=50, iv=[31, 31, 31, 31, 31, 31], ev=[0, 0, 0 ,0, 0, 0]):
        
        self.lv = lv
        self.iv = iv
        self.ev = ev
        self.moves = moves
        self.last_move_used = None
        self.name = json_data['Name']
        self.types = json_data['Types'] # convert str to list
        self.hp = self.calculate_hp(int(json_data['hp']), self.iv[0], self.ev[0])
        self.attack = self.calculate_other(int(json_data['attack']), self.iv[1], self.ev[1])
        self.defense = self.calculate_other(int(json_data['defense']), self.iv[2], self.ev[2])
        self.sp_attack = self.calculate_other(int(json_data['special_attack']), self.iv[3], self.ev[3])
        self.sp_defense = self.calculate_other(int(json_data['special_defense']), self.iv[4], self.ev[4])
        self.speed = self.calculate_other(int(json_data['speed']), self.iv[5], self.ev[5])

    # Calculation based on Gen I and II on Bulbapedia
    def calculate_hp(self, base, iv, ev):
        return math.floor(((2 * (base + iv) + math.floor(ev / 4)) * self.lv)/100) + self.lv + 10

    def calculate_other(self, base, iv, ev):
        return math.floor(math.floor(((2 * (base + iv) + math.floor(ev / 4)) * self.lv)/100) + 5)

    def update_hp(self, delta):
        self.hp += delta