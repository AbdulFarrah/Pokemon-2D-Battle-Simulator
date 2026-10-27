import random # type: ignore

class Player:
    def __init__(self, name, pokemons,game_mode,battle_size):
        self.name = name
        self.game_mode = game_mode
        self.pokemons = pokemons
        self.current_pokemon = pokemons[0]
        self.current_pokemon_index = 0
        self.remaining_pokemons = battle_size
    
    def handle_command(self, command, computer=0):
        while True:
            if command.lower() == 'fight':
                valid_moves = [i for i, move in enumerate(self.current_pokemon.moves) if move.pp > 0]
                if not valid_moves:
                    if computer:
                        bench = [i for i, pokemon in enumerate(self.pokemons)
                                 if pokemon.hp > 0 and i != self.current_pokemon_index]
                        if bench:
                            return ('switch', self.current_pokemon_index, random.choice(bench))
                    print("No moves have PP remaining. Switch Pokémon or exit the match.")
                    return None
                # choose a move
                for i, m in enumerate(self.current_pokemon.moves):
                    if len(self.current_pokemon.moves) > 1:
                        if (self.game_mode == "1" and computer == 0) or (self.game_mode == "2"):
                            print('({}): {} : ({}) ({}/{})'.format(i, m.name,m.type,m.pp, m.max_pp))
            
                while True:
                    try:
                        if self.game_mode == "1":
                            if computer != 0:
                                issued_move = random.choice(valid_moves)
                                break
                            elif computer == 0:
                                if len(valid_moves)==1:
                                    return (command.lower(), self.current_pokemon, valid_moves[0])
                                issued_move = int(input('Choose a move number : '))
                                if issued_move in valid_moves:
                                    break
                                else:
                                    print("Invalid move number. Please enter a number of a valid move.")
                        elif self.game_mode == "2":
                            if len(valid_moves)==1:
                                    return (command.lower(), self.current_pokemon, valid_moves[0])
                            issued_move = int(input('Choose a move number : '))
                            if issued_move in valid_moves:
                                break
                            else:
                                print("Invalid move number. Please enter a number of a valid move.")
                        else:
                            print(f"Unsupported game mode: {self.game_mode}")
                    except ValueError:
                        print("Invalid input. Please enter a valid integer.")
                return (command.lower(), self.current_pokemon, issued_move)
            elif command.lower() == 'switch':
                # display possible options of pokemons
                valid_switching_pokemons = [] # index of valid pokemons for switching
                for i, p in enumerate(self.pokemons):
                    if p.hp <= 0:
                        if (self.game_mode == "1" and computer == 0) or (self.game_mode == "2"):
                            print('({}): ({}){} (Fainted)'.format(i, ','.join(p.types),p.name))
                    else:
                        valid_switching_pokemons.append(i)
                        if (self.game_mode == "1" and computer == 0) or (self.game_mode == "2"):
                            print('({}): ({}){} '.format(i, ','.join(p.types),p.name))
                # switch current pokemon out for a pokemon on the bench
                while True:
                    try:
                        if self.game_mode == "1":
                            if computer != 0:
                                switched_pokemon = random.choice(valid_switching_pokemons)
                                break
                            elif computer == 0:
                                if len(valid_switching_pokemons) == 1:
                                    return (command.lower(), self.current_pokemon_index,valid_switching_pokemons[0])
                                switched_pokemon = int(input('Choose a Pokémon to switch out: '))
                                if switched_pokemon in valid_switching_pokemons:
                                    break
                                else:
                                    print("Invalid choice. Please enter a number for a valid Pokemon.")
                        elif self.game_mode == "2":
                            if len(valid_switching_pokemons) == 1:
                                    return (command.lower(), self.current_pokemon_index,valid_switching_pokemons[0])
                            switched_pokemon = int(input('Choose a Pokémon to switch out: '))
                            if switched_pokemon in valid_switching_pokemons:
                                break
                            else:
                                print("Invalid choice. Please enter a number for a valid Pokemon.")
                        else:
                            print(f"Unsupported game mode: {self.game_mode}")
                    except ValueError:
                        print("Invalid input. Please enter a valid integer.")
                return (command.lower(), self.current_pokemon_index, switched_pokemon)
            elif command.lower() == 'list': # list pokemons
                for i, p in enumerate(self.pokemons):
                    if p.hp <= 0:
                        print('({}): ({}){} (Fainted)'.format(i, ','.join(p.types),p.name))
                    else:
                        print('({}): ({}){} '.format(i, ','.join(p.types),p.name))
                return (command.lower(), None, None)
            elif command.lower() == 'exit':
                return (command.lower(), None, None)
