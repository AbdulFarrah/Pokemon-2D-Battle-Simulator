class Type:

    types = [
        'Normal',
        'Fire',
        'Water',
        'Electric',
        'Grass',
        'Ice',
        'Fighting',
        'Poison',
        'Ground',
        'Flying',
        'Psychic',
        'Bug',
        'Rock',
        'Ghost',
        'Dragon',
        'Dark',
        'Steel',
        'Fairy'
    ]

    # A\D   NOR  FIR  WAT  ELE  GRA  ICE  FIG  POI  GRO  FLY  PSY  BUG  ROC  GHO  DRA  DAR  STE  FAI
    table = [
    # NOR
            [1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1, 0.5,  0,   1,   1, 0.5,   1], 
    # FIR
            [1, 0.5, 0.5,   1,   2,   2,   1,   1,   1,   1,   1,   2, 0.5,  1, 0.5,   1,   2,   1], 
    # WAT
            [1,   2, 0.5,   1, 0.5,   1,   1,   1,   2,   1,   1,   1,   2,  1, 0.5,   1,   1,   1], 
    # ELE
            [1,   1,   2, 0.5, 0.5,   1,   1,   1,   0,   2,   1,   1,   1,  1, 0.5,   1,   1,   1], 
    # GRA
            [1, 0.5,   2,   1, 0.5,   1,   1, 0.5,   2, 0.5,   1, 0.5,   2,  1, 0.5,   1, 0.5,   1], 
    # ICE
            [1, 0.5, 0.5,   1,   2, 0.5,   1,   1,   2,   2,   1,   1,   1,  1,   2,   1, 0.5,   1], 
    # FIG
            [2,   1,   1,   1,   1,   2,   1, 0.5,   1, 0.5, 0.5, 0.5,   2,  0,   1,   2,   2, 0.5], 
    # POI
            [1,   1,   1,   1,   2,   1,   1, 0.5, 0.5,   1,   1,   1, 0.5, 0.5,   1,   1,   0,   2],
    # GRO
            [1,   2,   1,   2, 0.5,   1,   1,   2,   1,   0,   1, 0.5,   2,  1,   1,   1,   2,   1], 
    # FLY
            [1,   1,   1, 0.5,   2,   1,   2,   1,   1,   1,   1,   2, 0.5,  1,   1,   1, 0.5,   1], 
    # PSY
            [1,   1,   1,   1,   1,   1,   2,   2,   1,   1, 0.5,   1,   1,  1,   1,   0, 0.5,   1], 
    # BUG
            [1, 0.5,   1,   1,   2,   1, 0.5, 0.5,   1, 0.5,   2,   1,   1, 0.5,   1,   2, 0.5, 0.5],
    # ROC
            [1,   2,   1,   1,   1,   2, 0.5,   1, 0.5,   2,   1,   2,   1,  1,   1,   1, 0.5,   1], 
    # GHO
            [0,   1,   1,   1,   1,   1,   1,   1,   1,   1,   2,   1,   1,  2,   1, 0.5,   1,   1], 
    # DRA
            [1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,  1,   2,   1, 0.5,   0], 
    # DAR
            [1,   1,   1,   1,   1,   1, 0.5,   1,   1,   1,   2,   1,   1,  2,   1, 0.5,   1, 0.5], 
    # STE
            [1, 0.5, 0.5, 0.5,   1,   2,   1,   1,   1,   1,   1,   1,   2,  1,   1,   1, 0.5,   2], 
    # FAI
            [1, 0.5,   1,   1,   1,   1,   2, 0.5,   1,   1,   1,   1,   1,  1,   2,   2, 0.5,   1], 
    ]

    def __init__(self):
        pass

    def get_effectiveness(self, attack_type, defense_types):
        if not defense_types:
                print("[WARNING] No defense types provided. Defaulting effectiveness to 1.0")
                return 1.0
        try:
                attack_index = self.types.index(attack_type)
        except ValueError:
                print(f"[ERROR] Invalid attack type: {attack_type}. Defaulting to 1.0")
                return 1.0
        effectiveness = 1.0
        for defense_type in defense_types:
                try:
                        defense_index = self.types.index(defense_type)
                        effectiveness *= self.table[attack_index][defense_index]
                except ValueError:
                        print(f"[WARNING] Unknown defense type: {defense_type}. Ignoring.")
                        continue
        return effectiveness
