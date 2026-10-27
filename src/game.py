from .pokemon import Pokemon # type: ignore
from .move import Move # type: ignore
from .damage import Damage # type: ignore
from .player import Player # type: ignore
from copy import copy
import json
import random
import os
import re
import sys
import pygame # type: ignore
import socket
import threading
import time
from .network import ProtocolError, receive_message, send_message

class ConnectionLost(Exception):
    pass


class RuntimeDataError(RuntimeError):
    pass

class Game:
    special_moves = ["Blast Burn", "Eternabeam", "Frenzy Plant", "Giga Impact", "Hydro Cannon","Hyper Beam", "Meteor Assault", "Prismatic Laser", "Roar of Time","Rock Wrecker", "Shadow Half"]
    prepared_moves = ["Bounce","Dig","Dive","Electro Shot","Fly","Freeze Shock","Geomancy","Ice Burn","Meteor Beam","Phantom Force","Razor Wind","Shadow Force","Skull Bash","Sky Attack","Sky Drop","Solar Beam","SolarBeam","Solar Blade"]
    heal_user_moves = ["Recover", "Roost", "Slack Off", "Synthesis", "Soft-Boiled","Softboiled","Moonlight","Milk Drink", "Morning Sun", "Heal Order", "Shore Up", "Lunar Blessing"]
    heal_target_moves = ["Heal Pulse", "Floral Healing", "Wish", "Present"]
    drain_moves = ["Absorb", "Mega Drain", "Giga Drain", "Leech Life", "Drain Punch","Draining Kiss", "Horn Leech", "Oblivion Wing", "Parabolic Charge","Bitter Blade", "Matcha Gotcha", "Bouncy Bubble"]
    def __init__(self, settings, screen, runtime_data=None):
        self.graceful_exit = False
        self.connection_lost = threading.Event()
        self.gameOver = False
        self.forfeit_by = None
        self.scroll_offset = 0  
        self.move_log_stack = []
        self.move_hitted_stack = []
        self.fainted_pokemon = []
        self.pokemons, self.moves = runtime_data if runtime_data is not None else self.load_runtime_data()
        self.pokemon_images = self.load_pokemon_images()
        self.screen  = screen
        self.settings = settings
        self.screen_width, self.screen_height = self.screen.get_size()
        if settings['mode'] == "PvC":
            self.game_mode = "1"
        elif settings['mode'] == "PvP":
            self.game_mode = "2"
        else:
            self.game_mode = "3"
        if settings['generation'] == "ALL":
            self.gen = 0
        else:
            self.gen = settings['generation']
        self.conn = settings.get('conn', None)
        if self.game_mode == "3" and self.conn:
            threading.Thread(target=self.monitor_connection, args=(self.conn,), daemon=True).start()
        self.battle_size = settings['party_size']
        self.move_size = settings['move_size']
        self.player1 = Player(settings['player1_name'], self.generate_random_pokemons(settings['player1_name']), self.game_mode,self.battle_size)
        if self.game_mode == "1":
            self.player2 = Player(settings['player2_name'], self.generate_random_pokemons_for_computer(), self.game_mode,self.battle_size)
        elif self.game_mode == "2":
            self.player2 = Player(settings['player2_name'], self.generate_random_pokemons(settings['player2_name']), self.game_mode,self.battle_size)
        else:
            if settings['is_host']:
                self.send_player_info(self.player1)
                opp_name, opp_team,opp_battle_size = self.receive_opponent_info()
                if opp_name == settings['player1_name']:
                    opp_name=opp_name+"_"
            else:
                opp_name, opp_team,opp_battle_size = self.receive_opponent_info()
                self.send_player_info(self.player1)
                if opp_name == settings['player1_name']:
                    self.player1.name=self.player1.name+"_"
            self.player2 = Player(opp_name, opp_team, self.game_mode, opp_battle_size)
        self.player1.opponent = self.player2
        self.player2.opponent = self.player1
        self.display_team_summary_screen(self.player1)
        self.display_team_summary_screen(self.player2)
        self.damage = Damage()
        try:
            self.background_image = pygame.image.load(self.resource_path("data/Images/background.png")).convert()
        except (OSError, pygame.error) as exc:
            raise RuntimeDataError("The required data/Images/background.png file is missing or invalid.") from exc
        self.active_buttons = [] 
        self.selected_action = None 
        self.battle_message = ""
        self.pokemon_fade_alphas = {}  
        self.pokemon_fade_states = {}  
        self.attack_animation = None
        self.attack_animation_progress = 0
        self.attack_animation_duration = 30  
        self.attack_animation_attacker_pos = None
        self.attack_animation_target_pos = None
        self.attack_animation_active = False

    def get_events(self):
        if getattr(self, "connection_lost", None) is not None and self.connection_lost.is_set():
            self.connection_and_exit(self.screen)
        return pygame.event.get()

    def quit_game(self):
        pygame.quit()
        raise SystemExit

    @staticmethod
    def resource_path(relative_path):
        base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(base_path, relative_path)

    @classmethod
    def load_runtime_data(cls):
        loaded = []
        for relative_path, collection in (("data/pokemon.json", "pokemons"),
                                          ("data/data.json", "moves")):
            path = cls.resource_path(relative_path)
            try:
                with open(path, "r", encoding="utf-8") as source:
                    data = json.load(source)
            except (OSError, json.JSONDecodeError) as exc:
                raise RuntimeDataError(f"Could not load {relative_path}: {exc}") from exc
            if not isinstance(data, dict) or not isinstance(data.get(collection), list) or not data[collection]:
                raise RuntimeDataError(f"{relative_path} must contain a non-empty '{collection}' list.")
            loaded.append(data[collection])

        pokemons, moves = loaded
        required_stats = ("hp", "attack", "defense", "special_attack", "special_defense", "speed")
        for index, pokemon in enumerate(pokemons):
            if not isinstance(pokemon, dict):
                raise RuntimeDataError(f"Pokémon record {index} is not an object.")
            if (not isinstance(pokemon.get("Name"), str) or not pokemon["Name"]
                    or not isinstance(pokemon.get("Types"), list) or not pokemon["Types"]
                    or not isinstance(pokemon.get("Moves"), list)
                    or any(not isinstance(move_name, str) for move_name in pokemon["Moves"])
                    or type(pokemon.get("Generation")) is not int):
                raise RuntimeDataError(f"Pokémon record {index} is missing its name, types, or move list.")
            for stat in required_stats:
                if type(pokemon.get(stat)) not in (int, float) or pokemon[stat] <= 0:
                    raise RuntimeDataError(f"Pokémon {pokemon['Name']} has an invalid {stat} value.")
        for index, move in enumerate(moves):
            if not isinstance(move, dict) or any(not isinstance(move.get(field), str) or not move[field]
                                                  for field in ("Name", "Type", "Category", "Contest", "PP",
                                                                "Power", "Accuracy")):
                raise RuntimeDataError(f"Move record {index} is missing required fields.")
            try:
                if int(move["PP"]) <= 0:
                    raise ValueError
            except (ValueError, TypeError):
                raise RuntimeDataError(f"Move {move['Name']} has invalid PP data.")
        return pokemons, moves

    def finish_forfeit(self, forfeiting_player):
        winner = self.player2 if forfeiting_player is self.player1 else self.player1
        self.forfeit_by = forfeiting_player.name
        self.display_blackout_message([
            f"{forfeiting_player.name} forfeited the match...",
            f"{winner.name} wins!",
        ])
        self.gameOver = True
    
    def monitor_connection(self, conn):
        conn.settimeout(0.1)
        while True:
            if self.graceful_exit:
                return
            try:
                data = conn.recv(1, socket.MSG_PEEK)
                if data == b'':
                    break  
            except socket.timeout:
                pass
            except BlockingIOError:
                pass
            except (ConnectionResetError, ConnectionAbortedError, OSError):
                break
            time.sleep(0.1)
        if not self.graceful_exit:
            self.connection_lost.set()

    def connection_and_exit(self,screen):
        screen.fill((0, 0, 0))
        font = pygame.font.SysFont("arial", 48)
        text_surface = font.render("Other player disconnected. Exiting game.", True, (255, 0, 0))
        text_rect = text_surface.get_rect(center=(screen.get_width() // 2, screen.get_height() // 2))
        screen.blit(text_surface, text_rect)
        pygame.display.update()
        pygame.time.delay(3000)
        self.gameOver = True
        self.graceful_exit = True
        raise ConnectionLost("Opponent disconnected.")

    def send_player_info(self, player):
        data = {
            'type': 'team',
            'name': player.name,
            'team': [
                {'name': pokemon.name, 'moves': [move.name for move in pokemon.moves]}
                for pokemon in player.pokemons
            ],
            'battle_size': len(player.pokemons),
        }
        send_message(self.conn, data)

    def _decode_opponent_team(self, payload):
        if payload.get('type') != 'team':
            raise ProtocolError("Expected a team message.")
        name = payload.get('name')
        team_data = payload.get('team')
        battle_size = payload.get('battle_size')
        if not isinstance(name, str) or not name.strip() or len(name) > 32:
            raise ProtocolError("Invalid player name.")
        if type(battle_size) is not int or not 1 <= battle_size <= 6:
            raise ProtocolError("Invalid party size.")
        if not isinstance(team_data, list) or len(team_data) != battle_size:
            raise ProtocolError("Team size does not match the declared party size.")

        pokemon_by_name = {pokemon['Name']: pokemon for pokemon in self.pokemons}
        move_by_name = {move['Name']: move for move in self.moves}
        team = []
        used_names = set()
        for entry in team_data:
            if not isinstance(entry, dict):
                raise ProtocolError("Invalid Pokémon entry.")
            pokemon_name = entry.get('name')
            move_names = entry.get('moves')
            if not isinstance(pokemon_name, str) or pokemon_name not in pokemon_by_name:
                raise ProtocolError("Opponent selected an unknown Pokémon.")
            if pokemon_name in used_names:
                raise ProtocolError("Opponent team contains duplicate Pokémon.")
            used_names.add(pokemon_name)
            source = pokemon_by_name[pokemon_name]
            if not isinstance(move_names, list) or not 1 <= len(move_names) <= 10:
                raise ProtocolError("Invalid Pokémon move list.")
            if any(not isinstance(move_name, str) for move_name in move_names):
                raise ProtocolError("Invalid move name.")
            if len(set(move_names)) != len(move_names):
                raise ProtocolError("Pokémon move list contains duplicates.")
            if any(move_name not in source.get('Moves', []) or move_name not in move_by_name
                   for move_name in move_names):
                raise ProtocolError("Opponent selected a move that Pokémon cannot use.")
            moves = [Move(move_by_name[move_name]) for move_name in move_names]
            team.append(Pokemon(moves=moves, json_data=source))
        return name.strip(), team, battle_size

    def receive_opponent_info(self):
        return self._decode_opponent_team(receive_message(self.conn, pygame.event.pump))

    def send_player_move(self, action, arc):
        print(f"[DEBUG] Sending move: action={action}, accuracy={arc}")
        if not action:
            wire_action = {'kind': 'wait'}
        elif action[0] == 'fight':
            wire_action = {
                'kind': 'fight',
                'pokemon': action[1].name,
                'move_index': action[2],
            }
        elif action[0] == 'switch':
            wire_action = {'kind': 'switch', 'pokemon_index': action[2]}
        else:
            raise ProtocolError("Unsupported battle action.")
        send_message(self.conn, {'type': 'move', 'action': wire_action, 'accuracy': arc})


    def receive_opponent_move(self):
        print("[DEBUG] Waiting to receive opponent move...")
        msg = receive_message(self.conn, pygame.event.pump)
        if msg.get('type') != 'move' or not isinstance(msg.get('action'), dict):
            raise ProtocolError("Expected a move message.")
        accuracy = msg.get('accuracy')
        if accuracy is not None and (type(accuracy) is not int or not 1 <= accuracy <= 100):
            raise ProtocolError("Invalid move accuracy roll.")
        action_data = msg['action']
        kind = action_data.get('kind')
        if kind == 'wait':
            return [], accuracy
        if kind == 'fight':
            if accuracy is None:
                raise ProtocolError("Fight action is missing its accuracy roll.")
            pokemon_name = action_data.get('pokemon')
            move_index = action_data.get('move_index')
            opponent = self.player2
            if pokemon_name != opponent.current_pokemon.name:
                raise ProtocolError("Opponent action does not match its active Pokémon.")
            if type(move_index) is not int or not 0 <= move_index < len(opponent.current_pokemon.moves):
                raise ProtocolError("Invalid opponent move index.")
            if opponent.current_pokemon.moves[move_index].pp <= 0:
                raise ProtocolError("Opponent selected a move with no PP remaining.")
            return ('fight', opponent.current_pokemon, move_index), accuracy
        if kind == 'switch':
            pokemon_index = action_data.get('pokemon_index')
            opponent = self.player2
            if type(pokemon_index) is not int or not 0 <= pokemon_index < len(opponent.pokemons):
                raise ProtocolError("Invalid opponent switch index.")
            if opponent.pokemons[pokemon_index].hp <= 0 or pokemon_index == opponent.current_pokemon_index:
                raise ProtocolError("Opponent switch target is unavailable.")
            return ('switch', opponent.current_pokemon_index, pokemon_index), accuracy
        raise ProtocolError("Unsupported opponent action.")


    def sync_online_speed_tie(self, action1, action2):
        if self.settings['is_host']:
            winner = None
            if (action1 and len(action1) > 1 and action1[0] == 'fight'
                    and hasattr(action1[1], 'speed')
                    and action2 and len(action2) > 1 and action2[0] == 'fight'
                    and hasattr(action2[1], 'speed')
                    and action1[1].speed == action2[1].speed):
                winner = random.choice(('host', 'client'))
            send_message(self.conn, {'type': 'turn_sync', 'speed_tie_winner': winner})
        else:
            message = receive_message(self.conn, pygame.event.pump)
            if message.get('type') != 'turn_sync':
                raise ProtocolError("Expected a turn synchronization message.")
            winner = message.get('speed_tie_winner')
            if winner not in (None, 'host', 'client'):
                raise ProtocolError("Invalid speed-tie winner.")

        tie_expected = bool(
            action1 and len(action1) > 1 and action1[0] == 'fight'
            and action2 and len(action2) > 1 and action2[0] == 'fight'
            and action1[1].speed == action2[1].speed
        )
        if (winner is not None) != tie_expected:
            raise ProtocolError("Peers disagree about the turn's speed tie.")

        if winner is not None:
            local_won_tie = (winner == 'host') == self.settings['is_host']
            winning_player = self.player1 if local_won_tie else self.player2
            winning_player.current_pokemon.speed += 10
        return winner


    def send_switch_message(self, switch_index):
        print(f"[DEBUG] Sending switch message: index={switch_index}")
        send_message(self.conn, {'type': 'switch', 'switch_index': switch_index})


    def recv_switch_message(self):
        print("[DEBUG] Waiting to receive switch message...")
        msg = receive_message(self.conn, pygame.event.pump)
        index = msg.get('switch_index')
        if msg.get('type') != 'switch' or type(index) is not int:
            raise ProtocolError("Expected a valid switch message.")
        if not 0 <= index < len(self.player2.pokemons):
            raise ProtocolError("Opponent switch index is out of range.")
        if index == self.player2.current_pokemon_index or self.player2.pokemons[index].hp <= 0:
            raise ProtocolError("Opponent switch target is unavailable.")
        return index


    def start_fade_in(self, pokemon_name):
        self.pokemon_fade_alphas[pokemon_name] = 0
        self.pokemon_fade_states[pokemon_name] = 'fade_in'

    def start_fade_out(self, pokemon_name):
        self.pokemon_fade_alphas[pokemon_name] = 255
        self.pokemon_fade_states[pokemon_name] = 'fade_out'
        
    def generate_random_pokemons_for_computer(self):
        if self.gen == 0:
            eligible_pokemons = self.pokemons 
        else:
            eligible_pokemons = [p for p in self.pokemons if p['Generation'] == self.gen]
        random_pokemons = random.sample(eligible_pokemons, self.battle_size)
        pokemons = []
        for p in random_pokemons:
            learnable_moves = p['Moves']
            selected_moves = self.generate_random_moves(learnable_moves)
            pokemon = Pokemon(moves=selected_moves, json_data=p)
            pokemons.append(pokemon)
        return pokemons
    
    def load_pokemon_images(self):
        images = {}
        invalid_images = []
        for p in self.pokemons:
            name = p['Name']
            image_name = re.sub(r'[<>:"/\\\\|?*]', "_", name).replace(" ", "_")
            image_path_w = f"data/Images/{image_name}.png"
            image_path = self.resource_path(image_path_w)
            try:
                image = pygame.image.load(image_path).convert_alpha()
                images[name] = image
            except (OSError, pygame.error):
                invalid_images.append(image_name + ".png")
        if invalid_images:
            preview = ", ".join(invalid_images[:8])
            suffix = "..." if len(invalid_images) > 8 else ""
            raise RuntimeDataError(
                f"Missing or invalid Pokémon images ({len(invalid_images)}): {preview}{suffix}. "
                "Run data/image_fetcher.py to add or regenerate them."
            )
        return images
    
    def generate_random_pokemons(self, name):
        pokemons = []
        selected_indices = set()
        previous_selected_pokemons = []
        while len(pokemons) < self.battle_size:
            selected_pokemon = self.select_pokemon_by_number(name,previous_selected_pokemons)
            if isinstance(selected_pokemon, list):
                selected_pokemon = selected_pokemon[-1]
            idx = self.pokemons.index(selected_pokemon)
            if idx in selected_indices:
                continue
            selected_indices.add(idx)
            learnable_moves = selected_pokemon['Moves']
            selected_moves = self.generate_random_moves(learnable_moves)
            pokemon = Pokemon(moves=selected_moves, json_data=selected_pokemon)
            pokemons.append(pokemon)
        return pokemons

    def select_pokemon_by_number(self, player_name,previous_pokemons):
        filtered_pokemons = [p for p in self.pokemons if p['Generation'] == self.gen] if self.gen != 0 else self.pokemons
        clock = pygame.time.Clock()
        font = pygame.font.SysFont("DejaVu Sans", 24)
        small_font = pygame.font.Font(None, 20)
        selected_pokemons = previous_pokemons
        self.selected_pokemon_rects = []
        max_width = 80
        max_height = 80
        padding = 100
        num_columns = max(1, (self.screen_width - 150) // padding + 1)
        total_rows = (len(filtered_pokemons) + num_columns - 1) // num_columns
        visible_height = max(0, self.screen_height - 125)
        total_height = (total_rows - 1) * 120 + max_height if total_rows else 0
        max_scroll = max(0, total_height - visible_height)
        scroll_offset = 0
        scroll_speed = 120
        def scroll_by(delta):
            nonlocal scroll_offset
            scroll_offset = max(0, min(max_scroll, scroll_offset + delta))
        message = f"{player_name} will now choose {self.battle_size} Pokémon for your team."
        message_timer = 180  
        running = True
        delay_return = False
        while running:
            self.screen.fill((0, 0, 0))
            mouse_pos = pygame.mouse.get_pos()
            prompt = f"Select Pokémon {len(selected_pokemons) + 1} of {self.battle_size}:"
            prompt_surface = font.render(prompt, True, (0, 0, 0))
            prompt_bg_rect = pygame.Rect(40, 5, prompt_surface.get_width() + 20, 30)
            x, y = 50, 25 + prompt_bg_rect.height
            self.selected_pokemon_rects = []
            for pokemon in filtered_pokemons:
                name = pokemon['Name']
                image = self.pokemon_images.get(name)
                if image is None:
                    print(f"Missing image for: {name}")
                if image:
                    rect = self.display_pokemon_with_image(image, name,x, y - scroll_offset, pokemon)
                    if pokemon['Name'] in [p['Name'] for p in selected_pokemons]:
                        pygame.draw.rect(self.screen, (0, 255, 0), rect, 2)
                    elif rect.collidepoint(mouse_pos):
                        pygame.draw.rect(self.screen, (255, 255, 0), rect, 2)
                    x += padding
                    if x > self.screen_width - 100:
                        x = 50
                        y += 120
            info_box_rect = pygame.Rect(0, self.screen_height - 70, self.screen_width, 70)
            pygame.draw.rect(self.screen, (0, 0, 0), info_box_rect)
            scroll_surface = small_font.render("Use up/down arrow key or mouse wheel to scroll", True, (255, 255, 255))
            self.screen.blit(scroll_surface, (100, self.screen_height - 30))
            prompt = f"Select Pokémon {len(selected_pokemons) + 1} of {self.battle_size}:"
            prompt_surface = font.render(prompt, True, (255, 255, 255))
            prompt_bg_rect = pygame.Rect(40, 5, prompt_surface.get_width() + 20, 30)
            pygame.draw.rect(self.screen, (0, 0,0), prompt_bg_rect)
            self.screen.blit(prompt_surface, (50, 10))
            if message:
                message_surface = font.render(message, True, (255, 255, 255))
                self.screen.blit(message_surface, (100, self.screen_height - 60))
                if message_timer > 0:
                    message_timer -= 1
                else:
                    message = ""
            pygame.display.flip()
            for event in self.get_events():
                if event.type == pygame.QUIT:
                    self.quit_game()
                elif event.type == pygame.MOUSEWHEEL:
                    scroll_by(-event.y * scroll_speed)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (4, 5):
                    scroll_by(-scroll_speed if event.button == 4 else scroll_speed)
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    adjusted_mouse_pos = event.pos
                    for rect, pokemon in self.selected_pokemon_rects:
                        if rect.collidepoint(adjusted_mouse_pos):
                            if pokemon['Name'] in [p['Name'] for p in selected_pokemons]:
                                message = "You already selected this Pokémon. Choose a different one."
                                message_timer = 180
                            else:
                                selected_pokemons.append(pokemon)
                                message = f"{player_name} selected: {pokemon['Name']}"
                                message_timer = 180
                                delay_return = True
                            break
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_DOWN:
                        scroll_by(scroll_speed)
                    elif event.key == pygame.K_UP:
                        scroll_by(-scroll_speed)
                if delay_return:
                    self.screen.fill((0, 0, 0))
                    prompt = f"Select Pokémon {len(selected_pokemons) + 1} of {self.battle_size}:"
                    prompt_surface = font.render(prompt, True, (0, 0, 0))
                    prompt_bg_rect = pygame.Rect(40, 5, prompt_surface.get_width() + 20, 30)
                    x, y = 50, 25 + prompt_bg_rect.height
                    self.selected_pokemon_rects = []
                    for pokemon in filtered_pokemons:
                        name = pokemon['Name']
                        image = self.pokemon_images.get(name)
                        if image is None:
                            print(f"Missing image for: {name}")
                        if image:
                            rect = self.display_pokemon_with_image(image, name, x, y - scroll_offset, pokemon)
                            if pokemon['Name'] in [p['Name'] for p in selected_pokemons]:
                                pygame.draw.rect(self.screen, (0, 255, 0), rect, 2)
                            elif rect.collidepoint(mouse_pos):
                                pygame.draw.rect(self.screen, (255, 255, 0), rect, 2)
                            x += padding
                            if x > self.screen_width - 100:
                                x = 50
                                y += 120
                    info_box_rect = pygame.Rect(0, self.screen_height - 70, self.screen_width, 70)
                    pygame.draw.rect(self.screen, (0, 0, 0), info_box_rect)
                    scroll_surface = small_font.render("Use up/down arrow key or mouse wheel to scroll", True, (255, 255, 255))
                    self.screen.blit(scroll_surface, (100, self.screen_height - 30))
                    prompt = f"Select Pokémon {len(selected_pokemons) + 1} of {self.battle_size}:"
                    prompt_surface = font.render(prompt, True, (255, 255, 255))
                    prompt_bg_rect = pygame.Rect(40, 5, prompt_surface.get_width() + 20, 30)
                    pygame.draw.rect(self.screen, (0, 0, 0), prompt_bg_rect)
                    self.screen.blit(prompt_surface, (50, 10))
                    if message:
                        message_surface = font.render(message, True, (255, 255, 255))
                        self.screen.blit(message_surface, (100, self.screen_height - 60))
                    pygame.display.flip()
                    pygame.time.wait(500)
                    return selected_pokemons[-1]
            clock.tick(60)

    def display_pokemon_with_image(self, image, name, x, y, pokemon_data):
        screen = self.screen
        font = pygame.font.SysFont("DejaVu Sans", 20)  
        screen.blit(image, (x, y))
        rect = image.get_rect(topleft=(x, y))
        self.selected_pokemon_rects.append((rect, pokemon_data))
        name_text = font.render(name, True, (255, 255, 255))
        screen.blit(name_text, (x, y - 20))
        return rect

    def display_team_summary_screen(self, player):
        screen = self.screen
        SCREEN_WIDTH = self.screen.get_width()
        font = pygame.font.SysFont("DejaVu Sans", 26)
        small_font = pygame.font.SysFont("DejaVu Sans", 19)
        title_font = pygame.font.SysFont("DejaVu Sans", 42)
        running = True
        start_time = pygame.time.get_ticks()
        cols = 3
        padding = 20
        box_width = (SCREEN_WIDTH - (cols + 1) * padding) // cols
        box_height = 500  
        spacing = 20  
        pokemons = player.pokemons
        box_color = (30, 30, 60)
        text_color = (255, 255, 255)
        type_colors = {
            'Fire': (255, 100, 0), 'Water': (0, 150, 255), 'Grass': (0, 255, 0),
            'Electric': (255, 255, 0), 'Psychic': (255, 0, 255), 'Ice': (150, 255, 255),
            'Dragon': (100, 0, 255), 'Dark': (80, 80, 80), 'Fairy': (255, 182, 193),
            'Normal': (200, 200, 200), 'Fighting': (180, 0, 0), 'Flying': (135, 206, 235),
            'Poison': (160, 64, 160), 'Ground': (210, 180, 140), 'Rock': (184, 134, 11),
            'Bug': (154, 205, 50), 'Ghost': (75, 0, 130), 'Steel': (192, 192, 192)
        }
        scroll_offset = 0
        scroll_speed = 40
        while running:
            screen.fill((0, 0, 0))
            title_text = title_font.render(f"{player.name}'s Team", True, text_color)
            title_rect = title_text.get_rect(center=(SCREEN_WIDTH // 2, 40))
            screen.blit(title_text, title_rect)
            y_offset = 80 + scroll_offset
            x_offset = padding
            for idx, pokemon in enumerate(pokemons):
                box_rect = pygame.Rect(x_offset, y_offset, box_width, box_height)
                pygame.draw.rect(screen, box_color, box_rect, border_radius=12)
                name = pokemon.name
                name_surf = font.render(name, True, text_color)
                while name_surf.get_width() > box_width - 40 and font.get_height() > 10:
                    font = pygame.font.SysFont("DejaVu Sans", font.get_height() - 2)
                    name_surf = font.render(name, True, text_color)
                screen.blit(name_surf, (box_rect.x + 20, box_rect.y + 10))
                image = self.pokemon_images.get(pokemon.name, None)
                if image:
                    image = pygame.transform.scale(image, (96, 96))
                    screen.blit(image, (box_rect.x + 20, box_rect.y + 50))
                image_bottom = box_rect.y + 50 + 96
                types = pokemon.types if hasattr(pokemon, 'types') else []
                type_y = image_bottom + 10
                for t in types:
                    color = type_colors.get(t, (255, 255, 255))
                    type_surf = small_font.render(t, True, color)
                    screen.blit(type_surf, (box_rect.x + 20, type_y))
                    type_y += type_surf.get_height() + 2
                move_y = type_y + 10
                for move in (pokemon.moves):
                    move_surf = small_font.render(move.name, True, text_color)
                    screen.blit(move_surf, (box_rect.x + 20, move_y))
                    move_y += move_surf.get_height() + 2
                if (idx + 1) % cols == 0:
                    x_offset = padding
                    y_offset += box_height + spacing
                else:
                    x_offset += box_width + spacing
            for event in self.get_events():
                if event.type == pygame.QUIT:
                    self.quit_game()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        running = False  
                elif event.type == pygame.MOUSEWHEEL:
                    scroll_offset += event.y * scroll_speed
                    scroll_offset = min(0, scroll_offset) 
                    scroll_offset = max(-520, scroll_offset)
            pygame.display.flip()
            if pygame.time.get_ticks() - start_time > 5000:
                running = False
        screen.fill((0, 0, 0))
        pygame.display.flip()

    def display_blackout_message(self, messages, typing_speed=10):
        screen = self.screen
        clock = pygame.time.Clock()
        SCREEN_WIDTH = screen.get_width()
        SCREEN_HEIGHT = screen.get_height()
        screen.fill((0, 0, 0))
        pygame.display.flip()
        font = pygame.font.SysFont("DejaVu Sans", 32)
        line_height = font.get_height() + 20
        text_color = (255, 255, 255)
        total_height = line_height * len(messages)
        start_y = (SCREEN_HEIGHT - total_height) // 2
        displayed_lines = []
        for i, full_line in enumerate(messages):
            rendered_line = ""
            y = start_y + i * line_height
            for char in full_line:
                for event in self.get_events():
                    if event.type == pygame.QUIT:
                        self.quit_game()
                rendered_line += char
                displayed_lines.append((i, rendered_line))  
                screen.fill((0, 0, 0))
                for j in range(i):
                    text_surface = font.render(messages[j], True, text_color)
                    screen.blit(text_surface, ((SCREEN_WIDTH - text_surface.get_width()) // 2, start_y + j * line_height))
                text_surface = font.render(rendered_line, True, text_color)
                screen.blit(text_surface, ((SCREEN_WIDTH - text_surface.get_width()) // 2, y))
                pygame.display.flip()
                clock.tick(1000 // typing_speed)
            line_wait = 500
            start_time = pygame.time.get_ticks()
            while pygame.time.get_ticks() - start_time < line_wait:
                for event in self.get_events():
                    if event.type == pygame.QUIT:
                        self.quit_game()
                clock.tick(60)
        fade_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        fade_surface.fill((0, 0, 0))
        for alpha in range(0, 256, 10):
            for event in self.get_events():
                if event.type == pygame.QUIT:
                    self.quit_game()
            fade_surface.set_alpha(alpha)
            screen.blit(fade_surface, (0, 0))
            pygame.display.flip()
            clock.tick(60)

    def draw_top_info(self, turn, pokemon1, pokemon2):
        font = pygame.font.SysFont("DejaVu Sans", 22)
        top_rect = pygame.Rect(0, 0, self.screen.get_width(), 100)
        pygame.draw.rect(self.screen, (9, 74, 29), top_rect)
        if not hasattr(self, 'max_hp_tracker'):
            self.max_hp_tracker = {}
        def get_hp_info(pokemon):
            return pokemon.hp / pokemon.max_hp if pokemon.max_hp else 0
        lines = [
            f"Turn {turn}",
            f"({', '.join(pokemon1.types)}) {pokemon1.name}'s HP: {pokemon1.hp}",
            f".....VS.....",
            f"({', '.join(pokemon2.types)}) {pokemon2.name}'s HP: {pokemon2.hp}"
        ]
        for i, text in enumerate(lines):
            rendered = font.render(text, True, (255, 255, 255))
            text_rect = rendered.get_rect()
            text_rect.midleft = (self.screen.get_width() // 2 - text_rect.width // 2, 15 + i * 25)
            self.screen.blit(rendered, text_rect)
            if i == 1 or i == 3:
                pokemon = pokemon1 if i == 1 else pokemon2
                percent = get_hp_info(pokemon)
                bar_width = 200
                bar_height = 12
                bar_x = text_rect.right + 10  
                bar_y = text_rect.centery - bar_height // 2
                if percent > 0.5:
                    bar_color = (255, 255, 255)
                elif percent > 0.2:
                    bar_color = (255, 255, 0)
                else:
                    bar_color = (255, 0, 0)
                pygame.draw.rect(self.screen, (60, 60, 60), (bar_x, bar_y, bar_width, bar_height), border_radius=6)
                pygame.draw.rect(self.screen, bar_color, (bar_x, bar_y, int(bar_width * percent), bar_height), border_radius=6)
        pygame.display.update(top_rect)

    def draw_middle_area(self, pokemon1, pokemon2):
        fade_speed = 5
        poke_size = int(self.screen.get_width() * 0.15)
        poke1_x = int(self.screen.get_width() * 0.14)
        poke1_y = int(self.screen.get_height() * 0.3)
        poke2_x = int(self.screen.get_width() * 0.62)
        poke2_y = int(self.screen.get_height() * 0.18)
        bg = pygame.transform.scale(self.background_image, (self.screen.get_width(), 360))
        poke1_img = pygame.transform.scale(self.get_pokemon_image(pokemon1), (poke_size, poke_size))
        poke2_img = pygame.transform.scale(self.get_pokemon_image(pokemon2), (poke_size, poke_size))
        if not hasattr(self, 'prev_pokemon1'):
            self.prev_pokemon1 = None
        if not hasattr(self, 'prev_pokemon2'):
            self.prev_pokemon2 = None
        if not hasattr(self, 'pokemon_fade_states'):
            self.pokemon_fade_states = {}
        if not hasattr(self, 'pokemon_fade_alphas'):
            self.pokemon_fade_alphas = {}
        for p in [pokemon1.name, pokemon2.name]:
            self.pokemon_fade_alphas.setdefault(p, 0)
            self.pokemon_fade_states.setdefault(p, 'fade_in')
        if self.prev_pokemon1 and self.prev_pokemon1 != pokemon1.name:
            self.pokemon_fade_states[self.prev_pokemon1] = 'fade_out'
            self.pokemon_fade_states[pokemon1.name] = 'fade_in'
            self.pokemon_fade_alphas.setdefault(pokemon1.name, 0)
        if self.prev_pokemon2 and self.prev_pokemon2 != pokemon2.name:
            self.pokemon_fade_states[self.prev_pokemon2] = 'fade_out'
            self.pokemon_fade_states[pokemon2.name] = 'fade_in'
            self.pokemon_fade_alphas.setdefault(pokemon2.name, 0)
        fading = True
        clock = pygame.time.Clock()
        pygame.time.delay(500)
        while fading:
            middle_rect = pygame.Rect(0, 100, self.screen.get_width(), 360)
            self.screen.blit(bg, (0, 100))
            for p_name, state in self.pokemon_fade_states.items():
                if state == 'fade_in':
                    self.pokemon_fade_alphas[p_name] += fade_speed
                    if self.pokemon_fade_alphas[p_name] >= 255:
                        self.pokemon_fade_alphas[p_name] = 255
                        self.pokemon_fade_states[p_name] = None
                elif state == 'fade_out':
                    self.pokemon_fade_alphas[p_name] -= fade_speed
                    if self.pokemon_fade_alphas[p_name] <= 0:
                        self.pokemon_fade_alphas[p_name] = 0
                        self.pokemon_fade_states[p_name] = None
            for p, x, y, scaled_img in [(pokemon1, poke1_x, poke1_y, poke1_img), (pokemon2, poke2_x, poke2_y, poke2_img)]:
                alpha = self.pokemon_fade_alphas.get(p.name, 255)
                if alpha > 0:
                    temp_img = scaled_img.copy()
                    temp_img.set_alpha(alpha)
                    self.screen.blit(temp_img, (x, y))
            if self.attack_animation_active:
                progress = self.attack_animation_progress / self.attack_animation_duration
                start_pos = self.attack_animation_attacker_pos
                end_pos = self.attack_animation_target_pos
                current_x = start_pos[0] + (end_pos[0] - start_pos[0]) * progress
                current_y = start_pos[1] + (end_pos[1] - start_pos[1]) * progress
                pygame.draw.line(self.screen, (255, 255, 0), start_pos, (current_x, current_y), 5)
                self.attack_animation_progress += 1
                if self.attack_animation_progress > self.attack_animation_duration:
                    self.attack_animation_active = False
                    self.attack_animation_progress = 0
            pygame.display.update(middle_rect)
            fade_ongoing = any(state in ['fade_in', 'fade_out'] for state in self.pokemon_fade_states.values())
            if not fade_ongoing:
                fading = False
                self.prev_pokemon1 = pokemon1.name
                self.prev_pokemon2 = pokemon2.name
            for event in self.get_events():
                if event.type == pygame.QUIT:
                    self.quit_game()
            clock.tick(60)
        pygame.time.delay(500)  

    def draw_battle_message(self,delay = 0):
        msg_box = pygame.Rect(0, 420, self.screen.get_width(), 40)
        pygame.draw.rect(self.screen, (9, 74, 29), msg_box)
        pygame.draw.rect(self.screen, (255, 255, 255), msg_box, 2)
        font = pygame.font.SysFont("DejaVu Sans", 24)
        rendered_msg = font.render(self.battle_message, True, (255, 255, 255))
        self.screen.blit(rendered_msg, (20, 430))
        pygame.display.update(msg_box)
        if delay > 0:
            start_time = pygame.time.get_ticks()
            while pygame.time.get_ticks() - start_time < delay * 1000:
                for event in self.get_events():
                    if event.type == pygame.QUIT:
                        self.quit_game()
                pygame.time.wait(10)
    
    def draw_bottom_buttons(self, labels, clickable_names=None):
        self.bottom_buttons = []
        clickable_names = clickable_names or [label.split(" - ")[0] for label in labels]
        bottom_rect = pygame.Rect(0, 460, self.screen.get_width(), self.screen.get_height() - 460)
        pygame.draw.rect(self.screen, (40, 40, 40), bottom_rect)
        cols = 2
        rows = (len(labels) + 1) // 2
        screen_width = self.screen.get_width()
        screen_height = self.screen.get_height()
        area_height = screen_height - 460
        button_width = (screen_width - 3 * 50) // 2 
        vertical_spacing = (area_height - (rows * 50)) // (rows + 1)
        for i, label in enumerate(labels):
            col = i % cols
            row = i // cols
            x = 50 + col * (button_width + 50)
            y = 460 + vertical_spacing * (row + 1) + 50 * row
            rect = pygame.Rect(x, y, button_width, 50)
            is_clickable = label.split(" - ")[0] in clickable_names
            color = (70, 130, 180) if is_clickable else (100, 100, 100)
            pygame.draw.rect(self.screen, color, rect, border_radius=10)
            font = pygame.font.SysFont("DejaVu Sans", 24)
            text = font.render(label, True, (255, 255, 255))
            text_rect = text.get_rect(center=rect.center)
            self.screen.blit(text, text_rect)
            self.bottom_buttons.append((rect, label.split(" - ")[0] if is_clickable else None))
        pygame.display.update(bottom_rect)

    def get_button_click(self, event):
        if self.is_primary_mouse_down(event):
            mouse_pos = pygame.mouse.get_pos()
            for rect, label in self.bottom_buttons:
                if label and rect.collidepoint(mouse_pos):
                    return label
        return None

    @staticmethod
    def is_primary_mouse_down(event):
        return (event.type == pygame.MOUSEBUTTONDOWN
                and getattr(event, "button", 1) not in (4, 5))

    def process_move_hitted_animations(self, player1, player2):
        if not hasattr(self, 'move_hitted_stack') or len(self.move_hitted_stack) == 0:
            return
        type_colors = {
            'Fire': (255, 100, 0), 'Water': (0, 150, 255), 'Grass': (0, 255, 0),
            'Electric': (255, 255, 0), 'Psychic': (255, 0, 255), 'Ice': (150, 255, 255),
            'Dragon': (100, 0, 255), 'Dark': (80, 80, 80), 'Fairy': (255, 182, 193),
            'Normal': (200, 200, 200), 'Fighting': (180, 0, 0), 'Flying': (135, 206, 235),
            'Poison': (160, 64, 160), 'Ground': (210, 180, 140), 'Rock': (184, 134, 11),
            'Bug': (154, 205, 50), 'Ghost': (75, 0, 130), 'Steel': (192, 192, 192)
        }
        entries_to_process = self.move_hitted_stack[:2]
        screen_width = self.screen.get_width()
        screen_height = self.screen.get_height()
        poke_size = int(screen_width * 0.15)
        for entry in entries_to_process:
            try:
                player_split = entry.split("'s ", 1)
                player_name = player_split[0]
                rest = player_split[1]
                used_index = rest.index(" used ")
                against_index = rest.index(" against ")
                attacker_name = rest[:used_index]
                move_name = rest[used_index + len(" used "):against_index]
                target_name = rest[against_index + len(" against "):]
            except Exception as e:
                print(f"Error parsing entry for {player_name} | move_hitted_stack entry: {entry} — {e}")
                continue
            if player1.current_pokemon.name == attacker_name and player2.current_pokemon.name == target_name and player1.name == player_name:
                attacker = player1.current_pokemon
                target = player2.current_pokemon
            elif player2.current_pokemon.name == attacker_name and player1.current_pokemon.name == target_name and player2.name == player_name:
                attacker = player2.current_pokemon
                target = player1.current_pokemon
            else:
                continue
            move_type = next((mv.type for mv in attacker.moves if mv.name == move_name), 'Normal')
            beam_color = type_colors.get(move_type, (200, 200, 200))
            attacker_pos = (int(screen_width * 0.14), int(screen_height * 0.3)) if player1.current_pokemon == attacker else (int(screen_width * 0.62), int(screen_height * 0.18))
            target_pos = (int(screen_width * 0.62), int(screen_height * 0.18)) if player1.current_pokemon == attacker else (int(screen_width * 0.14), int(screen_height * 0.3))
            attacker_img = pygame.transform.scale(self.get_pokemon_image(attacker), (poke_size, poke_size))
            target_img = pygame.transform.scale(self.get_pokemon_image(target), (poke_size, poke_size))
            for _ in range(3):
                steps = 15
                for i in range(steps):
                    self.screen.fill((0, 0, 0)) 
                    self.screen.blit(attacker_img, attacker_pos)
                    self.screen.blit(target_img, target_pos)
                    start_x = attacker_pos[0] + poke_size // 2
                    start_y = attacker_pos[1] + poke_size // 2
                    end_x = target_pos[0] + poke_size // 2
                    end_y = target_pos[1] + poke_size // 2
                    dx = (end_x - start_x) / steps
                    dy = (end_y - start_y) / steps
                    segment_end = (start_x + dx * i, start_y + dy * i)
                    pygame.draw.line(self.screen, beam_color, (start_x, start_y), segment_end, 10)
                    pygame.display.flip()
                    pygame.time.delay(20)
                pygame.time.delay(300)
                pygame.display.flip()
                pygame.time.delay(300)
                for _ in range(2):
                    self.screen.fill((0, 0, 0))
                    self.screen.blit(attacker_img, attacker_pos)
                    pygame.display.flip()
                    pygame.time.delay(150)
                    self.screen.fill((0, 0, 0))
                    self.screen.blit(attacker_img, attacker_pos)
                    self.screen.blit(target_img, target_pos)
                    pygame.display.flip()
                    pygame.time.delay(150)
                pygame.time.delay(300)
                for _ in range(30):
                    x = end_x + random.randint(-20, 20)
                    y = end_y + random.randint(-20, 20)
                    radius = random.randint(2, 5)
                    pygame.draw.circle(self.screen, (180, 0, 0), (x, y), radius)
                pygame.display.flip()
                pygame.time.delay(100)
            self.screen.blit(attacker_img, attacker_pos)
            self.screen.blit(target_img, target_pos)
            pygame.display.flip()
            pygame.time.delay(600)
            if target.hp <= 0:
                pygame.time.delay(300)
                for _ in range(2):
                    for scale in [1.1, 0.9]:
                        temp_img = pygame.transform.scale(self.get_pokemon_image(target), (int(poke_size * scale), int(poke_size * scale)))
                        pos = (
                            target_pos[0] + (poke_size - temp_img.get_width()) // 2,
                            target_pos[1] + (poke_size - temp_img.get_height()) // 2
                        )
                        self.screen.fill((0, 0, 0))
                        self.screen.blit(attacker_img, attacker_pos)
                        self.screen.blit(temp_img, pos)
                        pygame.display.flip()
                        pygame.time.delay(150)
                for frame in range(14):
                    self.screen.fill((0, 0, 0))
                    self.screen.blit(attacker_img, attacker_pos)
                    for _ in range(25 + frame * 2):
                        x = target_pos[0] + poke_size // 2 + random.randint(-frame*4, frame*4)
                        y = target_pos[1] + poke_size // 2 + random.randint(-frame*4, frame*4)
                        radius = random.randint(3, 7)
                        red_shade = random.randint(130, 255)
                        pygame.draw.circle(self.screen, (red_shade, 0, 0), (x, y), radius)
                    pygame.display.flip()
                    pygame.time.delay(40)
        self.move_hitted_stack.clear()

    def handle_fight_command(self, player, computer=0):
        moves = player.current_pokemon.moves
        valid_moves = self.usable_move_indices(player.current_pokemon)
        if computer != 0:
            if valid_moves:
                return ('fight', player.current_pokemon, random.choice(valid_moves))
            bench = [index for index, pokemon in enumerate(player.pokemons)
                     if pokemon.hp > 0 and index != player.current_pokemon_index]
            return ('switch', player.current_pokemon_index, random.choice(bench)) if bench else []
        if not valid_moves:
            return None
        font = pygame.font.SysFont("DejaVu Sans", 28)
        self.scroll_offset = 0
        line_height = 50
        visible_height = self.screen.get_height() - 460
        max_scroll = max(0, len(moves) * line_height - visible_height)
        back_button = pygame.Rect(600, 470, 150, 50)
        button_rects = []
        def draw_moves():
            type_colors = {
            'Fire': (255, 100, 0), 'Water': (0, 150, 255), 'Grass': (0, 255, 0),
            'Electric': (255, 255, 0), 'Psychic': (255, 0, 255), 'Ice': (150, 255, 255),
            'Dragon': (100, 0, 255), 'Dark': (80, 80, 80), 'Fairy': (255, 182, 193),
            'Normal': (200, 200, 200), 'Fighting': (180, 0, 0), 'Flying': (135, 206, 235),
            'Poison': (160, 64, 160), 'Ground': (210, 180, 140), 'Rock': (184, 134, 11),
            'Bug': (154, 205, 50), 'Ghost': (75, 0, 130), 'Steel': (192, 192, 192)
            }
            nonlocal button_rects
            button_rects = []
            bottom_rect = pygame.Rect(0, 460, self.screen.get_width(), visible_height)
            pygame.draw.rect(self.screen, (40, 40, 40), bottom_rect)
            y_start = 470 - self.scroll_offset
            for i, move in enumerate(moves):
                y = y_start + i * line_height
                if 460 <= y <= 460 + visible_height:
                    button_rect = pygame.Rect(60, y, 400, line_height - 5)
                    color = type_colors.get(move.type, (70, 130, 180)) if move.pp > 0 else (90, 90, 90)
                    pygame.draw.rect(self.screen, color, button_rect)
                    pygame.draw.rect(self.screen, (255, 255, 255), button_rect, 2)
                    bg_color = type_colors.get(move.type, (70, 130, 180))
                    brightness = sum(bg_color) / 3
                    text_color = (0, 0, 0) if brightness > 150 else (255, 255, 255)
                    text_surface = font.render(f"{move.name}: ({move.type}) ({move.pp}/{move.max_pp})", True, text_color)
                    self.screen.blit(text_surface, (button_rect.x + 10, button_rect.y + 10))
                    if move.pp > 0:
                        button_rects.append((button_rect, move))
            pygame.draw.rect(self.screen, (180, 50, 50), back_button, border_radius=8)
            pygame.draw.rect(self.screen, (255, 255, 255), back_button, 2)
            back_text = font.render("Back", True, (255, 255, 255))
            self.screen.blit(back_text, (back_button.x + 30, back_button.y + 10))
            pygame.display.update(bottom_rect)
        draw_moves()
        selected_move = None
        clock = pygame.time.Clock()
        while selected_move is None:
            for event in self.get_events():
                if event.type == pygame.QUIT:
                    self.quit_game()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_DOWN:
                        self.scroll_offset = min(self.scroll_offset + line_height, max_scroll)
                        draw_moves()
                    elif event.key == pygame.K_UP:
                        self.scroll_offset = max(self.scroll_offset - line_height, 0)
                        draw_moves()
                    elif event.unicode.isdigit():
                        index = int(event.unicode) - 1
                        if index in valid_moves:
                            selected_move = index
                elif self.is_primary_mouse_down(event):
                    mx, my = event.pos
                    if back_button.collidepoint(mx, my):
                        bottom_rect = pygame.Rect(0, 460, self.screen.get_width(), visible_height)
                        pygame.draw.rect(self.screen, (0, 0, 0), bottom_rect)
                        pygame.display.update(bottom_rect)
                        return None
                    for rect, move in button_rects:
                        if rect.collidepoint(mx, my):
                            selected_move = moves.index(move)
                            break
            clock.tick(30)
        if selected_move is not None:
            bottom_rect = pygame.Rect(0, 460, self.screen.get_width(), visible_height)
            pygame.draw.rect(self.screen, (0, 0, 0), bottom_rect)
            pygame.display.update(bottom_rect)
        return ('fight', player.current_pokemon, selected_move)

    def handle_switch_command(self, player, fainted=False, computer=0):
        all_pokemon = []
        clickable = {}
        for i, p in enumerate(player.pokemons):
            label = f"{p.name} - HP: {p.hp}"
            if p.hp <= 0:
                label += " (Fainted)"
            elif i == player.current_pokemon_index:
                label += " (Active)"
            else:
                clickable[p.name] = i
            all_pokemon.append(label)
        if not clickable and not fainted:
            self.battle_message = "There are no Pokémon available to switch to."
            self.draw_battle_message(1.3)
            self.battle_message = ""
            self.draw_battle_message(0)
            return None
        if fainted:
            available = [i for i, p in enumerate(player.pokemons)
                        if p.hp > 0 and i != player.current_pokemon_index]
            if len(available) == 1:
                return ('switch', player.current_pokemon_index, available[0])
        if computer != 0:
            return ('switch', player.current_pokemon_index, random.choice(list(clickable.values())))
        font = pygame.font.SysFont("DejaVu Sans", 28)
        self.scroll_offset = 0
        line_height = 60
        visible_height = self.screen.get_height() - 460
        max_scroll = max(0, len(all_pokemon) * line_height - visible_height)
        back_button = pygame.Rect(600, 470, 150, 50)
        button_rects = []
        def draw_pokemon_list():
            nonlocal button_rects
            button_rects = []
            bottom_rect = pygame.Rect(0, 460, self.screen.get_width(), visible_height)
            pygame.draw.rect(self.screen, (40, 40, 40), bottom_rect)
            y_start = 470 - self.scroll_offset
            for i, label in enumerate(all_pokemon):
                y = y_start + i * line_height
                if 460 <= y <= 460 + visible_height:
                    button_rect = pygame.Rect(60, y, 500, line_height - 10)
                    name = label.split(" - ")[0]
                    is_clickable = name in clickable
                    color = (70, 130, 180) if is_clickable else (100, 100, 100)
                    pygame.draw.rect(self.screen, color, button_rect, border_radius=8)
                    pygame.draw.rect(self.screen, (255, 255, 255), button_rect, 2)
                    text_surface = font.render(label, True, (255, 255, 255))
                    self.screen.blit(text_surface, (button_rect.x + 10, button_rect.y + 15))
                    button_rects.append((button_rect, name if is_clickable else None))
            if not fainted:
                pygame.draw.rect(self.screen, (180, 50, 50), back_button, border_radius=8)
                pygame.draw.rect(self.screen, (255, 255, 255), back_button, 2)
                back_text = font.render("Back", True, (255, 255, 255))
                self.screen.blit(back_text, (back_button.x + 30, back_button.y + 10))
            pygame.display.update(bottom_rect)
        draw_pokemon_list()
        selected = None
        clock = pygame.time.Clock()
        while selected is None:
            for event in self.get_events():
                if event.type == pygame.QUIT:
                    self.quit_game()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_DOWN:
                        self.scroll_offset = min(self.scroll_offset + line_height, max_scroll)
                        draw_pokemon_list()
                    elif event.key == pygame.K_UP:
                        self.scroll_offset = max(self.scroll_offset - line_height, 0)
                        draw_pokemon_list()
                elif self.is_primary_mouse_down(event):
                    mx, my = event.pos
                    if not fainted and back_button.collidepoint(mx, my):
                        bottom_rect = pygame.Rect(0, 460, self.screen.get_width(), visible_height)
                        pygame.draw.rect(self.screen, (0, 0, 0), bottom_rect)
                        pygame.display.update(bottom_rect)
                        return None
                    for rect, name in button_rects:
                        if name and rect.collidepoint(mx, my):
                            selected = clickable.get(name)
                            break
            clock.tick(30)
        if selected is not None:
            bottom_rect = pygame.Rect(0, 460, self.screen.get_width(), visible_height)
            pygame.draw.rect(self.screen, (0, 0, 0), bottom_rect)
            pygame.display.update(bottom_rect)
        return ('switch', player.current_pokemon_index, selected)

    def handle_list_command(self, player):
        display_list = []
        for i, p in enumerate(player.pokemons):
            label = f"{p.name} - HP: {p.hp}"
            if p.hp <= 0:
                label += " (Fainted)"
            elif i == player.current_pokemon_index:
                label += " (Active)"
            display_list.append(label)
        font = pygame.font.SysFont("DejaVu Sans", 28)
        line_height = 50
        visible_height = self.screen.get_height() - 460
        max_scroll = max(0, len(display_list) * line_height - visible_height)
        scroll_offset = 0
        def draw_list():
            bottom_rect = pygame.Rect(0, 460, self.screen.get_width(), visible_height)
            pygame.draw.rect(self.screen, (40, 40, 40), bottom_rect)
            y_start = 470 - scroll_offset
            for i, label in enumerate(display_list):
                y = y_start + i * line_height
                if 460 <= y <= 460 + visible_height:
                    button_rect = pygame.Rect(60, y, 400, line_height - 5)
                    pygame.draw.rect(self.screen, (105, 105, 105), button_rect)
                    pygame.draw.rect(self.screen, (200, 200, 200), button_rect, 1)
                    text_surface = font.render(label, True, (255, 255, 255))
                    self.screen.blit(text_surface, (button_rect.x + 10, button_rect.y + 10))
            pygame.display.update(bottom_rect)
        draw_list()
        pygame.display.flip()
        start_time = pygame.time.get_ticks()
        clock = pygame.time.Clock()
        while True:
            now = pygame.time.get_ticks()
            if now - start_time > 5000:
                break
            for event in self.get_events():
                if event.type == pygame.QUIT:
                    self.quit_game()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_RETURN:
                        return
                    elif event.key == pygame.K_DOWN:
                        scroll_offset = min(scroll_offset + line_height, max_scroll)
                        draw_list()
                    elif event.key == pygame.K_UP:
                        scroll_offset = max(scroll_offset - line_height, 0)
                        draw_list()
            clock.tick(30)

    def generate_random_moves(self, learnable_moves):
        distinct_status_moves = set(
            self.heal_user_moves + self.heal_target_moves + self.drain_moves + ['Transform', 'Sketch']
        )
        learnable_names = set(learnable_moves)
        eligible = [move for move in self.moves
                    if move['Name'] in learnable_names
                    and not (move['Category'] == 'Status'
                             and move['Power'] == 'None'
                             and move['Name'] not in distinct_status_moves)]
        physical = [move for move in eligible if move['Category'] == 'Physical' and move['Power'] != 'None']
        special = [move for move in eligible if move['Category'] == 'Special' and move['Power'] != 'None']
        selected = random.sample(physical, min(len(physical), (self.move_size + 1) // 2))
        selected += random.sample(special, min(len(special), self.move_size - len(selected)))
        selected_names = {move['Name'] for move in selected}
        remaining = [move for move in eligible if move['Name'] not in selected_names]
        if len(selected) < self.move_size:
            selected += random.sample(remaining, min(len(remaining), self.move_size - len(selected)))
        return [Move(move) for move in selected]

    def fight(self, move, pokemon1, pokemon2,player,r_check):
        if getattr(move, 'pp', 1) <= 0:
            return
        self.move_log_stack.append(f"{pokemon1.name} used {move.name}")
        pokemon2.last_opponent_move_seen = copy(move)
        self.battle_message = f"{pokemon1.name} used {move.name}"
        self.draw_battle_message(1.3)
        self.battle_message = ""
        self.draw_battle_message(0)
        if move.accuracy == 100 or move.accuracy == 'None':
            damage_dealt = self.damage.calculate_damage(move, pokemon1, pokemon2)
        else:
            r = r_check
            if r <= move.accuracy:
                damage_dealt = self.damage.calculate_damage(move, pokemon1, pokemon2)
            else:
                damage_dealt = [0,0]
        if move.name == 'Transform':
            self.apply_transform(pokemon1, pokemon2)
        elif move.name == 'Sketch':
            self.apply_sketch(pokemon1)
        if (damage_dealt[0] == 0 and move.name not in self.heal_user_moves
                and move.name not in self.heal_target_moves
                and move.name not in ('Transform', 'Sketch')):
            self.battle_message = f"{pokemon2.name} avoided the attack..."
            self.draw_battle_message(1.3)
            self.battle_message = ""
            self.draw_battle_message(0)
        if damage_dealt[0] != 0:
            self.move_hitted_stack.append(f"{player.name}'s {pokemon1.name} used {move.name} against {pokemon2.name}")
        if(damage_dealt[1] != 0):
            pokemon1.update_hp(-damage_dealt[1])
            self.battle_message = f"{pokemon1.name} is hurt by recoil of {move.name}"
            self.draw_battle_message(1.3)
            self.battle_message = ""
            self.draw_battle_message(0)
        move.update_pp(-1)
        if (move.name in self.heal_user_moves):
            recovered = pokemon1.update_hp(pokemon1.max_hp // 2)
            self.battle_message = f"{pokemon1.name} recovered its HP by {recovered}..."
            self.draw_battle_message(1.3)    
            self.battle_message = ""
            self.draw_battle_message(0)  
        elif (move.name in self.heal_target_moves):
            recovered = pokemon2.update_hp(pokemon2.max_hp // 2)
            self.battle_message = f"{pokemon2.name} recovered its HP by {recovered}..."
            self.draw_battle_message(1.3)
            self.battle_message = ""
            self.draw_battle_message(0)
        elif (move.name in self.drain_moves):
            damage_removed = -pokemon2.update_hp(-damage_dealt[0])
            recovered = pokemon1.update_hp(damage_removed)
            self.battle_message = f"{pokemon1.name} recovered its HP by {recovered}..."
            self.draw_battle_message(1.3)   
            self.battle_message = ""
            self.draw_battle_message(0)    
        else:
            pokemon2.update_hp(-damage_dealt[0])

    def switch(self, player, pokemon_index):
        player.current_pokemon = player.pokemons[pokemon_index]
        player.current_pokemon_index = pokemon_index
        if player == self.player1:
            self.prev_pokemon1 = player.current_pokemon.name
        else:
            self.prev_pokemon2 = player.current_pokemon.name
        self.battle_message = f"Player {player.name} is switching  to {player.current_pokemon.name}..."
        self.draw_battle_message(1.3)
        self.battle_message = ""
        self.draw_battle_message(0)
    
    def check_fainting(self, pokemon):
        if pokemon.hp <= 0:
            pokemon.fainted = True
            pokemon.revert_transformation()
            return True
        return False

    @staticmethod
    def usable_move_indices(pokemon):
        return [index for index, move in enumerate(pokemon.moves) if move.pp > 0]

    def valid_commands(self, player):
        commands = ['fight'] if self.usable_move_indices(player.current_pokemon) else []
        commands.append('switch')
        commands.extend(('list', 'exit'))
        return commands

    def get_pokemon_image(self, pokemon):
        return pokemon.transformed_image or self.pokemon_images[pokemon.name]

    def apply_transform(self, pokemon, opponent):
        pokemon.transform_into(opponent.moves)
        pokemon.transformed_image = self.get_pokemon_image(opponent)

    def apply_sketch(self, pokemon):
        observed_move = pokemon.last_opponent_move_seen
        if observed_move is None:
            self.battle_message = "There is nothing to sketch."
            self.draw_battle_message(1.3)
            self.battle_message = ""
            self.draw_battle_message(0)
            return False

        sketch_index = next((index for index, move in enumerate(pokemon.moves)
                             if move.name.lower() == 'sketch'), None)
        if sketch_index is None:
            return False
        copied_move = copy(observed_move)
        copied_move.pp = copied_move.max_pp
        pokemon.moves[sketch_index] = copied_move
        self.battle_message = f"{pokemon.name} learned {copied_move.name}!"
        self.draw_battle_message(1.3)
        self.battle_message = ""
        self.draw_battle_message(0)
        return True

    def _record_fainted_players(self, *players):
        fainted_names = []
        for player in players:
            pokemon = player.current_pokemon
            if self.check_fainting(pokemon) and not pokemon.faint_recorded:
                pokemon.faint_recorded = True
                player.remaining_pokemons = max(0, player.remaining_pokemons - 1)
                self.fainted_pokemon.append(pokemon.name)
                fainted_names.append(player.name)
        return fainted_names

    def _resolve_fight_actions(self, ordered_actions):
        for attacker, defender, move_index, accuracy in ordered_actions:
            if attacker.current_pokemon.hp <= 0 or defender.current_pokemon.hp <= 0:
                break
            move = attacker.current_pokemon.moves[move_index]
            self.fight(move, attacker.current_pokemon, defender.current_pokemon, attacker, accuracy)
            fainted = self._record_fainted_players(attacker, defender)
            if fainted:
                return fainted
        return []

    def handle_fight_fight(self, player1, player2, move_index1, move_index2, arc1, arc2):
        first, second = (player1, player2) if player1.current_pokemon.speed > player2.current_pokemon.speed else (player2, player1)
        if player1.current_pokemon.speed == player2.current_pokemon.speed:
            first, second = random.choice(((player1, player2), (player2, player1)))
        indices = {player1: (move_index1, arc1), player2: (move_index2, arc2)}
        return self._resolve_fight_actions([
            (first, second, *indices[first]),
            (second, first, *indices[second]),
        ])

    def handle_switch_switch(self, player1, switched_pokemon1, player2, switched_pokemon2):
        self.switch(player1, switched_pokemon1)
        self.draw_middle_area(self.player1.current_pokemon, self.player2.current_pokemon)
        pygame.display.update()
        self.switch(player2, switched_pokemon2)
        self.draw_middle_area(self.player1.current_pokemon, self.player2.current_pokemon)
        pygame.display.update()
        
    def handle_rest_switch(self, player1, action1, player2, action2):
        if len(action2) < 1:
            self.switch(player1, action1[2])
            self.draw_middle_area(self.player1.current_pokemon, self.player2.current_pokemon)
            pygame.display.update()
        if len(action1) < 1:
            self.switch(player2, action2[2])
            self.draw_middle_area(self.player1.current_pokemon, self.player2.current_pokemon)
            pygame.display.update()

    def handle_rest_fight(self, player1, action1, player2, action2, arc1, arc2):
        if not action1 and action2 and action2[0] == 'fight':
            return self._resolve_fight_actions([(player2, player1, action2[2], arc2)])
        if not action2 and action1 and action1[0] == 'fight':
            return self._resolve_fight_actions([(player1, player2, action1[2], arc1)])
        return []

    def handle_switch_fight(self, player1, action1, player2, action2, arc1, arc2):
        if action1 and action1[0] == 'switch':
            self.switch(player1, action1[2])
            attacker, defender, accuracy, move_index = player2, player1, arc2, action2[2]
        else:
            self.switch(player2, action2[2])
            attacker, defender, accuracy, move_index = player1, player2, arc1, action1[2]
        self.draw_middle_area(self.player1.current_pokemon, self.player2.current_pokemon)
        pygame.display.update()
        return self._resolve_fight_actions([(attacker, defender, move_index, accuracy)])

    def prompt_player_command(self, player, valid_commands):
        command = None
        clock = pygame.time.Clock()
        while command not in valid_commands:
            self.battle_message = f"{player.name}'s Move"
            self.draw_battle_message(0)
            self.draw_bottom_buttons(valid_commands)
            waiting = True
            while waiting:
                for event in self.get_events():
                    if event.type == pygame.QUIT:
                        self.quit_game()
                    action = self.get_button_click(event)
                    if action in valid_commands:
                        command = action
                        self.battle_message = f"{player.name} chose: {command}"
                        self.draw_battle_message(0)
                        waiting = False
                clock.tick(30)
        return command
 
    def get_player_by_name(self, name):
        if self.player1.name == name:
            return self.player1
        else:
            return self.player2

    def game_loop(self):
        print("[DEBUG] Starting game loop.")
        turn = 1
        self.action1_copy = None
        self.action2_copy = None
        self.arc1_copy = None
        self.arc2_copy = None
        player_to_switch = []
        turn_clock = pygame.time.Clock()
        while not self.gameOver:
            PreparedFlag1 = False
            PreparedFlag2 = False
            print(f"[DEBUG] PreparedFlag1 = {PreparedFlag1},PreparedFlag2 = {PreparedFlag2}")
            print(f"[DEBUG] Starting turn {turn}")
            arc1 = None
            arc2 = None
            self.screen.fill((0, 0, 0))
            valid_commands = self.valid_commands(self.player1)
            print("[DEBUG] Drawing battle UI elements.")
            self.draw_top_info(turn, self.player1.current_pokemon, self.player2.current_pokemon)
            self.draw_middle_area(self.player1.current_pokemon, self.player2.current_pokemon)
            self.draw_battle_message()
            self.draw_bottom_buttons(valid_commands)
            pygame.display.flip()
            if (turn > 1 and self.action1_copy):
                print("[DEBUG] Using stored action1_copy and arc1_copy from previous turn.")
                action1 = self.action1_copy
                arc1 = self.arc1_copy
                self.action1_copy = None
                self.arc1_copy = None
                PreparedFlag1 = True
            elif (turn > 1 and action1 and not isinstance(action1[1], int)
                    and self.player1.current_pokemon.name == action1[1].name
                    and action1[1].moves[action1[2]].name in self.special_moves):
                print("[DEBUG] Player1 is resting from special move.")
                self.battle_message = f'{self.player1.current_pokemon.name} is still resting...'
                self.draw_battle_message(1.3)
                self.battle_message = ""
                self.draw_battle_message(0)
                action1 = []
            else:
                print("[DEBUG] Awaiting Player1 input...")
                command = None
                waiting = True
                self.battle_message = f"{self.player1.name}'s Move"
                self.draw_battle_message(0)
                print(f"[DEBUG] {self.battle_message}")
                while waiting:
                    for event in self.get_events():
                        if event.type == pygame.QUIT:
                            print("[DEBUG] Quit event detected. Exiting game.")
                            self.quit_game()
                        action = self.get_button_click(event)
                        if action in valid_commands:
                            command = action
                            print(f"[DEBUG] Player1 chose: {command}")
                            self.battle_message = f"{self.player1.name} chose: {command}"
                            self.draw_battle_message(0)
                            print(f"[DEBUG] {self.battle_message}")
                            waiting = False
                    turn_clock.tick(30)
                if command == 'fight':
                    print("[DEBUG] Handling fight command for Player1.")
                    result = self.handle_fight_command(self.player1)
                    if result is None:
                        print("[DEBUG] Fight command returned None. Skipping turn.")
                        continue
                    action1 = result
                    arc1 = random.randint(1, 100)
                    print(f"[DEBUG] action1: {action1}, arc1: {arc1}")
                elif command == 'switch':
                    print("[DEBUG] Handling switch command for Player1.")
                    result = self.handle_switch_command(self.player1)
                    if result is None:
                        print("[DEBUG] Switch command returned None. Skipping turn.")
                        continue
                    action1 = result
                    print(f"[DEBUG] action1: {action1}")
                elif command == 'list':
                    print("[DEBUG] Listing Pokémon for Player1.")
                    self.handle_list_command(self.player1)
                    continue
                elif command == 'exit':
                    print("[DEBUG] Exit command received. Ending game.")
                    self.battle_message = "Bye..."
                    self.draw_battle_message(0.5)
                    print(f"[DEBUG] {self.battle_message}")
                    if self.game_mode == "2":
                        self.finish_forfeit(self.player1)
                    else:
                        self.gameOver = True
                    break
                if (action1 and action1[1] is not None and not isinstance(action1[1], int)
                    and self.player1.current_pokemon.name == action1[1].name
                    and action1[1].moves[action1[2]].name in self.prepared_moves):
                    move_name = action1[1].moves[action1[2]].name
                    print(f"[DEBUG] Player1 is preparing to use {move_name}.")
                    self.battle_message = f'{self.player1.current_pokemon.name} is preparing to use {move_name}...'
                    self.draw_battle_message(1.3)
                    print(f"[DEBUG] {self.battle_message}")
                    self.battle_message = ""
                    self.draw_battle_message(0)
                    self.action1_copy = action1
                    self.arc1_copy = arc1
                    action1 = []
                    arc1 = None
            if (turn > 1 and self.action2_copy):
                print("[DEBUG] Using stored action2_copy and arc2_copy from previous turn.")
                action2 = self.action2_copy
                arc2 = self.arc2_copy
                self.action2_copy = None
                self.arc2_copy = None
                PreparedFlag2 = True
            elif (turn > 1 and 'action2' in locals() and action2 and not isinstance(action2[1], int)
                and self.player2.current_pokemon.name == action2[1].name
                and action2[1].moves[action2[2]].name in self.special_moves):
                print("[DEBUG] Player2 is still resting from special move.")
                self.battle_message = f'{self.player2.current_pokemon.name} is still resting...'
                self.draw_battle_message(1.3)
                print(f"[DEBUG] {self.battle_message}")
                self.battle_message = ""
                self.draw_battle_message(0)
                action2 = []
            else:
                print(f"[DEBUG] Entering player2 move selection block. game_mode = {self.game_mode}")
                if self.game_mode == "1":
                    print("[DEBUG] Game mode 1: AI selecting fight move for Player2.")
                    command = "fight"
                    action2 = self.handle_fight_command(self.player2, 1)
                    arc2 = random.randint(1, 100)
                    print(f"[DEBUG] AI action2: {action2}, arc2: {arc2}")
                elif self.game_mode == "2":
                    print("[DEBUG] Game mode 2: Player2 choosing manually.")
                    while True:
                        command = self.prompt_player_command(self.player2, self.valid_commands(self.player2))
                        print(f"[DEBUG] Player2 entered command: {command}")
                        if command == 'list':
                            print("[DEBUG] Listing Player2 Pokémon.")
                            self.handle_list_command(self.player2)
                            continue
                        elif command == 'fight':
                            print("[DEBUG] Handling fight command for Player2.")
                            result = self.handle_fight_command(self.player2)
                            if result is None:
                                print("[DEBUG] Fight command returned None. Retrying.")
                                continue
                            action2 = result
                            arc2 = random.randint(1, 100)
                            print(f"[DEBUG] action2: {action2}, arc2: {arc2}")
                            break
                        elif command == 'switch':
                            print("[DEBUG] Handling switch command for Player2.")
                            result = self.handle_switch_command(self.player2)
                            if result is None:
                                print("[DEBUG] Switch command returned None. Retrying.")
                                continue
                            action2 = result
                            print(f"[DEBUG] action2: {action2}")
                            break
                        elif command == 'exit':
                            print("[DEBUG] Exit command received from Player2. Ending game.")
                            self.battle_message = "Bye..."
                            self.draw_battle_message(0.5)
                            print(f"[DEBUG] {self.battle_message}")
                            self.finish_forfeit(self.player2)
                            break
            if self.gameOver:
                break
            if self.game_mode == "3":
                print("[DEBUG] Entered game_mode 3 block.")
                effective_action1 = self.action1_copy if self.action1_copy else action1
                effective_arc1 = self.arc1_copy if self.arc1_copy else arc1
                print(f"[DEBUG] effective_action1: {effective_action1}")
                print(f"[DEBUG] effective_arc1: {effective_arc1}")
                if self.settings['is_host']:
                    if not PreparedFlag1:
                        print("[DEBUG] I am HOST. Sending move...")
                        self.send_player_move(effective_action1, effective_arc1)
                    if not PreparedFlag2:
                        print("[DEBUG] Waiting to receive opponent move...")
                        action2, arc2 = self.receive_opponent_move()
                        print(f"[DEBUG] Received action2: {action2}, arc2: {arc2}")
                        if action2 is None:
                            print("[DEBUG] action2 is None. Replacing with empty list.")
                            action2 = []
                else:
                    if not PreparedFlag2:
                        print("[DEBUG] I am CLIENT. Waiting to receive opponent move...")
                        action2, arc2 = self.receive_opponent_move()
                        print(f"[DEBUG] Received action2: {action2}, arc2: {arc2}")
                        if action2 is None:
                            print("[DEBUG] action2 is None. Replacing with empty list.")
                            action2 = []
                    if not PreparedFlag1:
                        print("[DEBUG] Sending my move now...")
                        self.send_player_move(effective_action1, effective_arc1)
                winner = self.sync_online_speed_tie(effective_action1, action2)
                if winner is not None:
                    print(f"[DEBUG] {winner} won the speed tie; both sides apply the same boost.")
                if (action2 and len(action2) > 1 and action2[1] is not None and not isinstance(action2[1], int)
                    and self.player2.current_pokemon.name == action2[1].name
                    and action2[1].moves[action2[2]].name in self.prepared_moves and not PreparedFlag2) :
                    move_name = action2[1].moves[action2[2]].name
                    print(f"[DEBUG] Player2 is preparing move: {move_name}")
                    self.battle_message = f'{self.player2.current_pokemon.name} is preparing to use {move_name}...'
                    self.draw_battle_message(1.3)
                    print(f"[DEBUG] {self.battle_message}")
                    self.battle_message = ""
                    self.draw_battle_message(0)
                    self.action2_copy = action2
                    self.arc2_copy = arc2
                    action2 = []
                    arc2 = None
            print(f"[DEBUG] Pre-resolution action1: {action1}, action2: {action2}")
            if not action1 and not action2:
                print("[DEBUG] No actions from either side. Advancing turn.")
                turn += 1
                continue
            elif (not action1 and action2 and action2[0] == 'fight') or (not action2 and action1 and action1[0] == 'fight'):
                print("[DEBUG] Condition met: One player resting, other using fight.")
                print(f"[DEBUG] Evaluated: not action1={not action1}, action2={action2}, action2[0]==fight={action2 and action2[0] == 'fight'}")
                print(f"[DEBUG] OR condition: action2={action2}, not action2={not action2}, action1={action1}, action1[0]==fight={action1 and action1[0] == 'fight'}")
                print("[DEBUG] Handling rest vs fight scenario.")
                player_to_switch = self.handle_rest_fight(self.player1, action1, self.player2, action2, arc1, arc2)
                if action1 and len(action1) > 0 and hasattr(action1[1], "moves"):
                    move_name = action1[1].moves[action1[2]].name
                    print(f"[DEBUG] Player1 used move: {move_name}")
                if action2 and len(action2) > 0 and hasattr(action2[1], "moves"):
                    move_name = action2[1].moves[action2[2]].name
                    print(f"[DEBUG] Player2 used move: {move_name}")
            elif (not action1 and action2 and action2[0] == 'switch') or (not action2 and action1 and action1[0] == 'switch'):
                print("[DEBUG] Condition met: One player resting, other switching.")
                print(f"[DEBUG] Evaluated: not action1={not action1}, action2={action2}, action2[0]==switch={action2 and action2[0] == 'switch'}")
                print(f"[DEBUG] OR condition: action2={action2}, not action2={not action2}, action1={action1}, action1[0]==switch={action1 and action1[0] == 'switch'}")
                print("[DEBUG] Handling rest vs switch scenario.")
                self.handle_rest_switch(self.player1, action1, self.player2, action2)
            elif action1 and action1[0] == 'fight' and action2 and action2[0] == 'fight':
                print("[DEBUG] Condition met: Both players used fight.")
                print(f"[DEBUG] action1[0]: {action1[0]}, action2[0]: {action2[0]}")
                print("[DEBUG] Handling fight vs fight scenario.")
                player_to_switch = self.handle_fight_fight(self.player1, self.player2, action1[2], action2[2], arc1, arc2)
                if action1 and hasattr(action1[1], "moves"):
                    move_name = action1[1].moves[action1[2]].name
                    print(f"[DEBUG] Player1 used move: {move_name}")
                if action2 and hasattr(action2[1], "moves"):
                    move_name = action2[1].moves[action2[2]].name
                    print(f"[DEBUG] Player2 used move: {move_name}")
            elif action1 and action1[0] == 'switch' and action2 and action2[0] == 'switch':
                print("[DEBUG] Condition met: Both players used switch.")
                print(f"[DEBUG] action1[0]: {action1[0]}, action2[0]: {action2[0]}")
                print("[DEBUG] Handling switch vs switch scenario.")
                self.handle_switch_switch(self.player1, action1[2], self.player2, action2[2])
            else:
                print("[DEBUG] Reached fallback else block.")
                print(f"[DEBUG] action1: {action1}, action2: {action2}")
                if action2:
                    print("[DEBUG] action2 is truthy. Assuming switch vs fight scenario.")
                    print("[DEBUG] Handling switch vs fight scenario.")
                    player_to_switch = self.handle_switch_fight(self.player1, action1, self.player2, action2, arc1, arc2)
                else:
                    print("[DEBUG] action2 is falsy. No matching scenario found. Skipping resolution.")
            print("[DEBUG] called UI funtion to draw middle area")
            self.draw_middle_area(self.player1.current_pokemon, self.player2.current_pokemon)
            print("[DEBUG] called UI funtion to draw move animation")
            self.process_move_hitted_animations(self.player1, self.player2)
            if self.fainted_pokemon:
                print(f"[DEBUG] Fainted Pokémon detected: {self.fainted_pokemon}")
                for name in self.fainted_pokemon:
                    self.battle_message = f"{name} fainted..."
                    print(f"[DEBUG] Displaying faint message for: {name}")
                    self.draw_battle_message(1.3)
                    self.battle_message = ""
                    self.draw_battle_message(0)
                self.fainted_pokemon = []
                print("[DEBUG] Cleared fainted_pokemon list.")
            if self.player1.remaining_pokemons == 0 or self.player2.remaining_pokemons == 0:
                print(f"[DEBUG] Checking for game over condition: P1 remaining = {self.player1.remaining_pokemons}, P2 remaining = {self.player2.remaining_pokemons}")
                if self.player1.remaining_pokemons == 0 and self.player2.remaining_pokemons == 0:
                    print("[DEBUG] Both players have no Pokémon left. It's a tie.")
                    messages = [
                        f"All Pokémon of {self.player1.name} have blacked out...",
                        f"All Pokémon of {self.player2.name} have blacked out...",
                        "The Match is a Tie!",
                        f"{self.player1.name} rushed to the nearest Pokécenter!",
                        f"{self.player2.name} rushed to the nearest Pokécenter!"
                    ]
                elif self.player1.remaining_pokemons == 0:
                    print(f"[DEBUG] {self.player1.name} has no Pokémon left. {self.player2.name} wins.")
                    messages = [
                        f"All Pokémon of {self.player1.name} have blacked out...",
                        f"{self.player2.name} wins!",
                        f"{self.player1.name} rushed to the nearest Pokécenter!"
                    ]
                else:
                    print(f"[DEBUG] {self.player2.name} has no Pokémon left. {self.player1.name} wins.")
                    messages = [
                        f"All Pokémon of {self.player2.name} have blacked out...",
                        f"{self.player1.name} wins!",
                        f"{self.player2.name} rushed to the nearest Pokécenter!"
                    ]
                print("[DEBUG] Displaying blackout messages...")
                self.display_blackout_message(messages)
                print("[DEBUG] Setting gameOver and graceful_exit to True.")
                self.gameOver = True
                self.graceful_exit = True
                continue
            if player_to_switch and len(player_to_switch) > 0 and self.player1.remaining_pokemons != 0 and self.player2.remaining_pokemons != 0:
                if self.game_mode == "3":
                    print("[DEBUG] Entered faint switch handling in game_mode 3.")
                    if self.settings['is_host']:
                        print("[DEBUG] This side is HOST.")
                        my_name = self.player1.name
                        opponent_name = self.player2.name
                    else:
                        print("[DEBUG] This side is CLIENT.")
                        my_name = self.player1.name
                        opponent_name = self.player2.name
                    print(f"[DEBUG] my_name = {my_name}, opponent_name = {opponent_name}")
                    print(f"[DEBUG] player_to_switch = {player_to_switch}")
                    if my_name in player_to_switch and opponent_name in player_to_switch:
                        print("[DEBUG] Both players need to switch.")
                        my_player = self.get_player_by_name(my_name)
                        opp_player = self.get_player_by_name(opponent_name)
                        my_avail_indexes = [i for i, poke in enumerate(my_player.pokemons) if poke.hp > 0]
                        print(f"[DEBUG] My available Pokémon indexes: {my_avail_indexes}")
                        if len(my_avail_indexes) == 1:
                            print(f"[DEBUG] Only one available Pokémon. Auto-switching to index {my_avail_indexes[0]}")
                            self.switch(my_player, my_avail_indexes[0])
                            self.draw_middle_area(self.player1.current_pokemon, self.player2.current_pokemon)
                            pygame.display.update()
                            print("[DEBUG] Sending switch index to opponent...")
                            self.send_switch_message(my_avail_indexes[0])
                        else:
                            print("[DEBUG] Prompting player for switch (fainted=True)...")
                            action = self.handle_switch_command(my_player, fainted=True)
                            print(f"[DEBUG] Player chose switch index {action[2]}")
                            self.switch(my_player, action[2])
                            self.draw_middle_area(self.player1.current_pokemon, self.player2.current_pokemon)
                            pygame.display.update()
                            print("[DEBUG] Sending switch index to opponent...")
                            self.send_switch_message(action[2])
                        print("[DEBUG] Waiting for opponent to switch...")
                        self.battle_message = "Waiting for opponent to switch..."
                        self.draw_battle_message(1.3)
                        opp_switch_ind = self.recv_switch_message()
                        print(f"[DEBUG] Received opponent switch index: {opp_switch_ind}")
                        self.switch(opp_player, opp_switch_ind)
                        self.draw_middle_area(self.player1.current_pokemon, self.player2.current_pokemon)
                        pygame.display.update()
                    elif my_name in player_to_switch:
                        print("[DEBUG] Only this player needs to switch.")
                        my_player = self.get_player_by_name(my_name)
                        my_avail_indexes = [i for i, poke in enumerate(my_player.pokemons) if poke.hp > 0]
                        print(f"[DEBUG] My available Pokémon indexes: {my_avail_indexes}")
                        if len(my_avail_indexes) == 1:
                            print(f"[DEBUG] Only one available Pokémon. Auto-switching to index {my_avail_indexes[0]}")
                            self.switch(my_player, my_avail_indexes[0])
                            self.draw_middle_area(self.player1.current_pokemon, self.player2.current_pokemon)
                            pygame.display.update()
                            print("[DEBUG] Sending switch index to opponent...")
                            self.send_switch_message(my_avail_indexes[0])
                        else:
                            print("[DEBUG] Prompting player for switch (fainted=True)...")
                            action = self.handle_switch_command(my_player, fainted=True)
                            print(f"[DEBUG] Player chose switch index {action[2]}")
                            self.switch(my_player, action[2])
                            self.draw_middle_area(self.player1.current_pokemon, self.player2.current_pokemon)
                            pygame.display.update()
                            print("[DEBUG] Sending switch index to opponent...")
                            self.send_switch_message(action[2])
                    elif opponent_name in player_to_switch:
                        print("[DEBUG] Only opponent needs to switch.")
                        self.battle_message = "Opponent's Pokémon fainted, waiting for them to switch..."
                        self.draw_battle_message(1.3)
                        opp_player = self.get_player_by_name(opponent_name)
                        print("[DEBUG] Waiting to receive opponent switch index...")
                        opp_switch_ind = self.recv_switch_message()
                        print(f"[DEBUG] Received opponent switch index: {opp_switch_ind}")
                        self.switch(opp_player, opp_switch_ind)
                        self.draw_middle_area(self.player1.current_pokemon, self.player2.current_pokemon)
                        pygame.display.update()
                else:
                    if self.player1.name in player_to_switch:
                        print(f"[DEBUG] {self.player1.name} needs to switch.")
                        p1_avail_indexes = [i for i, poke in enumerate(self.player1.pokemons) if poke.hp > 0]
                        print(f"[DEBUG] {self.player1.name} available Pokémon indexes: {p1_avail_indexes}")
                        if len(p1_avail_indexes) == 1:
                            print(f"[DEBUG] Only one option. Automatically switching to index {p1_avail_indexes[0]}")
                            self.switch(self.player1, p1_avail_indexes[0])
                            self.draw_middle_area(self.player1.current_pokemon, self.player2.current_pokemon)
                            pygame.display.update()
                        else:
                            print("[DEBUG] Prompting player1 to choose switch.")
                            action = self.handle_switch_command(self.player1, fainted=True)
                            print(f"[DEBUG] Player1 chose to switch to index {action[2]}")
                            self.switch(self.player1, action[2])
                            self.draw_middle_area(self.player1.current_pokemon, self.player2.current_pokemon)
                            pygame.display.update()
                    if self.player2.name in player_to_switch:
                        print(f"[DEBUG] {self.player2.name} needs to switch.")
                        p2_avail_indexes = [i for i, poke in enumerate(self.player2.pokemons) if poke.hp > 0]
                        print(f"[DEBUG] {self.player2.name} available Pokémon indexes: {p2_avail_indexes}")
                        if len(p2_avail_indexes) == 1:
                            print(f"[DEBUG] Only one option. Automatically switching to index {p2_avail_indexes[0]}")
                            self.switch(self.player2, p2_avail_indexes[0])
                            self.draw_middle_area(self.player1.current_pokemon, self.player2.current_pokemon)
                            pygame.display.update()
                        else:
                            if self.game_mode == "1":
                                print("[DEBUG] Game mode 1: using AI to choose switch for player2.")
                                action = self.player2.handle_command('switch', 1)
                                print(f"[DEBUG] AI chose to switch to index {action[2]}")
                                self.switch(self.player2, action[2])
                                self.draw_middle_area(self.player1.current_pokemon, self.player2.current_pokemon)
                                pygame.display.update()
                            else:
                                print("[DEBUG] Prompting player2 to choose switch.")
                                action = self.handle_switch_command(self.player2, fainted=True)
                                print(f"[DEBUG] Player2 chose to switch to index {action[2]}")
                                self.switch(self.player2, action[2])
                                self.draw_middle_area(self.player1.current_pokemon, self.player2.current_pokemon)
                                pygame.display.update()
                print("[DEBUG] End of switch block. Clearing player_to_switch.")
                player_to_switch = []
            turn += 1
        self.graceful_exit = True
