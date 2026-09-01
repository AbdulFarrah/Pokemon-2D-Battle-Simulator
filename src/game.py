from .pokemon import Pokemon # type: ignore
from .move import Move # type: ignore
from .damage import Damage # type: ignore
from .player import Player # type: ignore
from collections import Counter
import json
import random
import os
import sys
import pygame # type: ignore
import pickle
import socket
import threading
import time
import ctypes

def raise_exception_in_main_thread(exc_type):
    main_thread = threading.main_thread()
    for thread_id, frame in sys._current_frames().items():
        if thread_id == main_thread.ident:
            ctypes.pythonapi.PyThreadState_SetAsyncExc(
                ctypes.c_long(thread_id),
                ctypes.py_object(exc_type)
            )
            break

class ConnectionLost(Exception):
    pass

class Game:
    special_moves = ["Blast Burn", "Eternabeam", "Frenzy Plant", "Giga Impact", "Hydro Cannon","Hyper Beam", "Meteor Assault", "Prismatic Laser", "Roar of Time","Rock Wrecker", "Shadow Half"]
    prepared_moves = ["Bounce","Dig","Dive","Electro Shot","Fly","Freeze Shock","Geomancy","Ice Burn","Meteor Beam","Phantom Force","Razor Wind","Shadow Force","Skull Bash","Sky Attack","Sky Drop","Solar Beam","SolarBeam","Solar Blade"]
    heal_user_moves = ["Recover", "Roost", "Slack Off", "Synthesis", "Soft-Boiled","Softboiled","Moonlight","Milk Drink", "Morning Sun", "Heal Order", "Shore Up", "Lunar Blessing"]
    heal_target_moves = ["Heal Pulse", "Floral Healing", "Wish", "Present"]
    drain_moves = ["Absorb", "Mega Drain", "Giga Drain", "Leech Life", "Drain Punch","Draining Kiss", "Horn Leech", "Oblivion Wing", "Parabolic Charge","Bitter Blade", "Matcha Gotcha", "Bouncy Bubble"]
    move_log_stack = []
    move_hitted_stack = []
    fainted_pokemon = []
    def __init__(self, settings,screen):
        self.graceful_exit = False
        self.gameOver = False
        self.scroll_offset = 0  
        with open(self.resource_path('data/pokemon.json'), 'r') as infile:
            data = json.load(infile)
            self.pokemons = data['pokemons']
        with open(self.resource_path('data/data.json'), 'r') as infile:
            data = json.load(infile)
            self.moves = data['moves']
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
        self.background_image = pygame.image.load(self.resource_path("data/Images/background.png")).convert()
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

    def quit_game(self):
        pygame.quit()
        raise SystemExit
    
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
            self.connection_and_exit(self.screen)

    def connection_and_exit(self,screen):
        screen.fill((0, 0, 0))
        font = pygame.font.SysFont("arial", 48)
        text_surface = font.render("Other player disconnected. Exiting game.", True, (255, 0, 0))
        text_rect = text_surface.get_rect(center=(screen.get_width() // 2, screen.get_height() // 2))
        screen.blit(text_surface, text_rect)
        pygame.display.update()
        pygame.time.delay(3000)
        self.gameOver = True
        raise_exception_in_main_thread(ConnectionLost)

    def send_player_info(self, player):
        data = {
            'name': player.name,
            'team': player.pokemons,
            'battle_size': self.battle_size,
        }
        self.conn.sendall(pickle.dumps(data))

    def receive_opponent_info(self):
        data = b''
        opponent_data = None
        while True:
            try:
                part = self.conn.recv(4096)
                if not part:
                    break
                data += part
                try:
                    opponent_data = pickle.loads(data)
                    break
                except pickle.UnpicklingError:
                    continue
            except socket.timeout:
                continue
        if opponent_data is None:
            raise ValueError("Failed to receive valid opponent data.")
        return opponent_data['name'], opponent_data['team'],opponent_data['battle_size']

    def send_player_move(self, action, arc):
        print(f"[DEBUG] Sending move: action={action}, accuracy={arc}")
        data = {
            'type': 'move',
            'action': action,
            'accuracy': arc
        }
        self.conn.sendall(pickle.dumps(data))


    def receive_opponent_move(self):
        import pickle
        import pygame # type: ignore
        import socket
        print("[DEBUG] Waiting to receive opponent move...")
        data = b''
        self.conn.settimeout(0.1)
        while True:
            pygame.event.pump()
            try:
                part = self.conn.recv(4096)
                if not part:
                    continue
                data += part
                try:
                    msg = pickle.loads(data)
                    if isinstance(msg, dict) and msg.get("type") == "move":
                        print(f"[DEBUG] Received move message: {msg}")
                        if 'action' in msg and 'accuracy' in msg:
                            return msg['action'], msg['accuracy']
                        else:
                            print("[⚠️] Incomplete move data:", msg)
                            data = b''
                            continue
                    else:
                        print("[⚠️] Skipped non-move message:", msg)
                        data = b''
                        continue
                except pickle.UnpicklingError:
                    continue
            except socket.timeout:
                continue
            except Exception as e:
                print(f"[ERROR] receive_opponent_move: {e}")
                break
        return None, None


    def send_switch_message(self, switch_index):
        print(f"[DEBUG] Sending switch message: index={switch_index}")
        data = {
            'type': 'switch',
            'switch_index': switch_index
        }
        self.conn.sendall(pickle.dumps(data))


    def recv_switch_message(self):
        import pickle
        data = b''
        print("[DEBUG] Waiting to receive switch message...")
        while True:
            try:
                chunk = self.conn.recv(4096)
                if not chunk:
                    continue
                data += chunk
                msg = pickle.loads(data)
                if isinstance(msg, dict) and msg.get("type") == "switch":
                    print(f"[DEBUG] Received switch message: {msg}")
                    return msg['switch_index']
                else:
                    print("[⚠️] Skipped non-switch message:", msg)
                    data = b''
                    continue
            except Exception as e:
                print(f"[ERROR] recv_switch_message: {e}")
                continue


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
        for p in self.pokemons:
            name = p['Name']
            image_name = name.replace(" ", "_")
            image_path_w = f"data/Images/{image_name}.png"
            image_path = self.resource_path(image_path_w)
            if os.path.exists(image_path):
                image = pygame.image.load(image_path).convert_alpha()
                images[name] = image
        return images

    def resource_path(self,relative_path):
        try:
            base_path = sys._MEIPASS
        except AttributeError:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)
    
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
        num_columns = self.screen_width // (max_width + padding)
        total_rows = (len(filtered_pokemons) // num_columns) + (1 if len(filtered_pokemons) % num_columns != 0 else 0)
        total_height = total_rows * (max_height + 20)
        max_scroll_y = max(total_height - self.screen_height, 0)
        scroll_y = 0
        scroll_speed = 180
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
                    rect = self.display_pokemon_with_image(image, name,x, y + scroll_y, pokemon)
                    if pokemon['Name'] in [p['Name'] for p in selected_pokemons]:
                        pygame.draw.rect(self.screen, (0, 255, 0), rect, 2)
                    elif rect.collidepoint(mouse_pos):
                        pygame.draw.rect(self.screen, (255, 255, 0), rect, 2)
                    self.selected_pokemon_rects.append((rect, pokemon))
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
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.quit_game()
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
                    if event.key == pygame.K_DOWN and scroll_y < 0:
                        scroll_y += scroll_speed
                    elif event.key == pygame.K_UP and scroll_y > -(max_scroll_y - 550):
                        scroll_y -= scroll_speed
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
                            rect = self.display_pokemon_with_image(image, name, x, y + scroll_y, pokemon)
                            if pokemon['Name'] in [p['Name'] for p in selected_pokemons]:
                                pygame.draw.rect(self.screen, (0, 255, 0), rect, 2)
                            elif rect.collidepoint(mouse_pos):
                                pygame.draw.rect(self.screen, (255, 255, 0), rect, 2)
                            self.selected_pokemon_rects.append((rect, pokemon))
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
            for event in pygame.event.get():
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
                for event in pygame.event.get():
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
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.quit_game()
                clock.tick(60)
        fade_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        fade_surface.fill((0, 0, 0))
        for alpha in range(0, 256, 10):
            for event in pygame.event.get():
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
            unique_id = id(pokemon)
            if unique_id not in self.max_hp_tracker:
                self.max_hp_tracker[unique_id] = pokemon.hp
            max_hp = self.max_hp_tracker[unique_id]
            current_hp = max(0, pokemon.hp)
            return current_hp / max_hp if max_hp else 0
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
        poke1_img = pygame.transform.scale(self.pokemon_images[pokemon1.name], (poke_size, poke_size))
        poke2_img = pygame.transform.scale(self.pokemon_images[pokemon2.name], (poke_size, poke_size))
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
            for event in pygame.event.get():
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
                for event in pygame.event.get():
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
        if event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = pygame.mouse.get_pos()
            for rect, label in self.bottom_buttons:
                if label and rect.collidepoint(mouse_pos):
                    return label
        return None

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
            attacker_img = pygame.transform.scale(self.pokemon_images[attacker.name], (poke_size, poke_size))
            target_img = pygame.transform.scale(self.pokemon_images[target.name], (poke_size, poke_size))
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
                        temp_img = pygame.transform.scale(self.pokemon_images[target.name], (int(poke_size * scale), int(poke_size * scale)))
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
        if computer != 0:
            valid_moves = list(range(len(moves)))
            return ('fight', player.current_pokemon, random.choice(valid_moves))
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
                    pygame.draw.rect(self.screen, type_colors.get(move.type, (70, 130, 180)), button_rect)
                    pygame.draw.rect(self.screen, (255, 255, 255), button_rect, 2)
                    bg_color = type_colors.get(move.type, (70, 130, 180))
                    brightness = sum(bg_color) / 3
                    text_color = (0, 0, 0) if brightness > 150 else (255, 255, 255)
                    text_surface = font.render(f"{move.name}: ({move.type}) ({move.pp}/{move.max_pp})", True, text_color)
                    self.screen.blit(text_surface, (button_rect.x + 10, button_rect.y + 10))
                    button_rects.append((button_rect, move))
            pygame.draw.rect(self.screen, (180, 50, 50), back_button, border_radius=8)
            pygame.draw.rect(self.screen, (255, 255, 255), back_button, 2)
            back_text = font.render("Back", True, (255, 255, 255))
            self.screen.blit(back_text, (back_button.x + 30, back_button.y + 10))
            pygame.display.update(bottom_rect)
        draw_moves()
        selected_move = None
        while selected_move is None:
            for event in pygame.event.get():
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
                        if 0 <= index < len(moves):
                            selected_move = moves[index]
                elif event.type == pygame.MOUSEBUTTONDOWN:
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
        while selected is None:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.quit_game()
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_DOWN:
                        self.scroll_offset = min(self.scroll_offset + line_height, max_scroll)
                        draw_pokemon_list()
                    elif event.key == pygame.K_UP:
                        self.scroll_offset = max(self.scroll_offset - line_height, 0)
                        draw_pokemon_list()
                elif event.type == pygame.MOUSEBUTTONDOWN:
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
        while True:
            now = pygame.time.get_ticks()
            if now - start_time > 5000:
                break
            for event in pygame.event.get():
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

    def generate_random_moves(self, learnable_moves):
        physical_moves = []
        special_moves = []
        for m in self.moves:
            if m['Name'] in learnable_moves:
                if m['Category'] == 'Physical' and m['Power'] != 'None': 
                    physical_moves.append(m)
                elif m['Category'] == 'Special' and m['Power'] != 'None':
                    special_moves.append(m)
        if len(physical_moves) > ((self.move_size + 1)//2):
            random_physical_moves = random.sample(physical_moves, ((self.move_size + 1)//2))
        else:
            random_physical_moves = physical_moves
        if len(special_moves) > (self.move_size - len(random_physical_moves)):
            random_special_moves = random.sample(special_moves, self.move_size - len(random_physical_moves))
        else:
            random_special_moves = special_moves
        move_list = random_physical_moves + random_special_moves
        if len(move_list) < self.move_size:
            num_moves_to_select = min((self.move_size-len(move_list)), len(learnable_moves))
            available_moves = [move for move in set(learnable_moves) if move not in move_list]
            move_l = random.sample(available_moves,num_moves_to_select)
            for m in self.moves:
                if m['Name'] in move_l:
                    move_list.append(m)
        name_counts = Counter(m['Name'] for m in move_list)
        output = []
        for m in move_list:
            if name_counts[m['Name']] == 1:
                output.append(Move(m))
        if len(output) < self.move_size:
            existing_names = {m.name for m in output}
            additional_moves = [m for m in self.moves if m['Name'] in learnable_moves and m['Name'] not in existing_names]
            for m in additional_moves:
                output.append(Move(m))
                existing_names.add(m['Name'])
                if len(output) == self.move_size:
                    break
        return output

    def fight(self, move, pokemon1, pokemon2,player,r_check):
        self.move_log_stack.append(f"{pokemon1.name} used {move.name}")
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
        if damage_dealt[0] == 0 and move.name not in self.heal_user_moves and move.name not in self.heal_target_moves and move.name != 'Transform' and move.name != 'Sketch':
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
            pokemon1.update_hp(+50)
            self.battle_message = f"{pokemon1.name} recovered its HP by 50..."  
            self.draw_battle_message(1.3)    
            self.battle_message = ""
            self.draw_battle_message(0)  
        elif (move.name in self.heal_target_moves):
            pokemon2.update_hp(+50)
            self.battle_message = f"{pokemon2.name} recovered its HP by 50..."
            self.draw_battle_message(1.3)
            self.battle_message = ""
            self.draw_battle_message(0)
        elif (move.name in self.drain_moves):
            pokemon2.update_hp(-damage_dealt[0])
            pokemon1.update_hp(+(damage_dealt[0] // 4))
            self.battle_message = f"{pokemon1.name} recovered its HP by {damage_dealt[0] // 4}..." 
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
            return True
        return False

    def handle_fight_fight(self, player1, player2, move_index1, move_index2,arc1,arc2):
        pokemon1 = player1.current_pokemon
        pokemon2 = player2.current_pokemon
        move1 = pokemon1.moves[move_index1]
        move2 = pokemon2.moves[move_index2]
        if pokemon1.speed > pokemon2.speed:
            self.fight(move1, pokemon1, pokemon2,player1,arc1)
            if self.check_fainting(pokemon1) and self.check_fainting(pokemon2):
                self.fainted_pokemon.append(pokemon1.name)
                self.fainted_pokemon.append(pokemon2.name)
                player1.remaining_pokemons -= 1
                player2.remaining_pokemons -= 1
                return [player1.name, player2.name]
            if self.check_fainting(pokemon1):
                self.fainted_pokemon.append(pokemon1.name)
                player1.remaining_pokemons -= 1
                return [player1.name]
            if self.check_fainting(pokemon2):
                self.fainted_pokemon.append(pokemon2.name)
                player2.remaining_pokemons -= 1
                return [player2.name]
            self.fight(move2, pokemon2, pokemon1,player2,arc2)
            if self.check_fainting(pokemon2) and self.check_fainting(pokemon1):
                self.fainted_pokemon.append(pokemon1.name)
                self.fainted_pokemon.append(pokemon2.name)
                player1.remaining_pokemons -= 1
                player2.remaining_pokemons -= 1
                return [player1.name, player2.name]
            if self.check_fainting(pokemon1):
                self.fainted_pokemon.append(pokemon1.name)
                player1.remaining_pokemons -= 1
                return [player1.name]
            if self.check_fainting(pokemon2):
                self.fainted_pokemon.append(pokemon2.name)
                player2.remaining_pokemons -= 1
                return [player2.name]
        elif pokemon1.speed < pokemon2.speed:
            self.fight(move2, pokemon2, pokemon1,player2,arc2)
            if self.check_fainting(pokemon2) and self.check_fainting(pokemon1):
                self.fainted_pokemon.append(pokemon2.name)
                self.fainted_pokemon.append(pokemon1.name)
                player1.remaining_pokemons -= 1
                player2.remaining_pokemons -= 1
                return [player1.name, player2.name]
            if self.check_fainting(pokemon1):
                self.fainted_pokemon.append(pokemon1.name)
                player1.remaining_pokemons -= 1
                return [player1.name]
            if self.check_fainting(pokemon2):
                self.fainted_pokemon.append(pokemon2.name)
                player2.remaining_pokemons -= 1
                return [player2.name]
            self.fight(move1, pokemon1, pokemon2,player1,arc1)
            if self.check_fainting(pokemon1) and self.check_fainting(pokemon2):
                self.fainted_pokemon.append(pokemon1.name)
                self.fainted_pokemon.append(pokemon2.name)
                player1.remaining_pokemons -= 1
                player2.remaining_pokemons -= 1
                return [player1.name, player2.name]
            if self.check_fainting(pokemon1):
                self.fainted_pokemon.append(pokemon1.name)
                player1.remaining_pokemons -= 1
                return [player1.name]
            if self.check_fainting(pokemon2):
                self.fainted_pokemon.append(pokemon2.name)
                player2.remaining_pokemons -= 1
                return [player2.name]
        else:
            random_pokemon = random.randint(1, 2)
            if random_pokemon == 1:
                self.fight(move1, pokemon1, pokemon2,player1,arc1)
                if self.check_fainting(pokemon1) and self.check_fainting(pokemon2):
                    self.fainted_pokemon.append(pokemon1.name)
                    self.fainted_pokemon.append(pokemon2.name)
                    player1.remaining_pokemons -= 1
                    player2.remaining_pokemons -= 1
                    return [player1.name, player2.name]
                if self.check_fainting(pokemon1):
                    self.fainted_pokemon.append(pokemon1.name)
                    player1.remaining_pokemons -= 1
                    return [player1.name]
                if self.check_fainting(pokemon2):
                    self.fainted_pokemon.append(pokemon2.name)
                    player2.remaining_pokemons -= 1
                    return [player2.name]
                self.fight(move2, pokemon2, pokemon1,player2,arc2)
                if self.check_fainting(pokemon2) and self.check_fainting(pokemon1):
                    self.fainted_pokemon.append(pokemon2.name)
                    self.fainted_pokemon.append(pokemon1.name) 
                    player1.remaining_pokemons -= 1
                    player2.remaining_pokemons -= 1
                    return [player1.name, player2.name]
                if self.check_fainting(pokemon1):
                    self.fainted_pokemon.append(pokemon1.name)
                    player1.remaining_pokemons -= 1
                    return [player1.name]
                if self.check_fainting(pokemon2):
                    self.fainted_pokemon.append(pokemon2.name)
                    player2.remaining_pokemons -= 1
                    return [player2.name]
            else:
                self.fight(move2, pokemon2, pokemon1,player2,arc2)
                if self.check_fainting(pokemon2) and self.check_fainting(pokemon1):
                    self.fainted_pokemon.append(pokemon2.name)
                    self.fainted_pokemon.append(pokemon1.name)
                    player1.remaining_pokemons -= 1
                    player2.remaining_pokemons -= 1
                    return [player1.name, player2.name]
                if self.check_fainting(pokemon1):
                    self.fainted_pokemon.append(pokemon1.name)
                    player1.remaining_pokemons -= 1
                    return [player1.name]
                if self.check_fainting(pokemon2):
                    self.fainted_pokemon.append(pokemon2.name)
                    player2.remaining_pokemons -= 1
                    return [player2.name]
                self.fight(move1, pokemon1, pokemon2,player1,arc1)
                if self.check_fainting(pokemon1) and self.check_fainting(pokemon2):
                    self.fainted_pokemon.append(pokemon1.name)
                    self.fainted_pokemon.append(pokemon2.name)
                    player1.remaining_pokemons -= 1
                    player2.remaining_pokemons -= 1
                    return [player1.name, player2.name]
                if self.check_fainting(pokemon1):
                    self.fainted_pokemon.append(pokemon1.name)
                    player1.remaining_pokemons -= 1
                    return [player1.name]
                if self.check_fainting(pokemon2):
                    self.fainted_pokemon.append(pokemon2.name)
                    player2.remaining_pokemons -= 1
                    return [player2.name]

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
        print(f"[DEBUG] Entered handle_rest_fight()")
        print(f"[DEBUG] action1: {action1}, action2: {action2}")
        if len(action1) < 1:
            print("[DEBUG] Player1 is resting. Player2 is attacking.")
            move2 = player2.current_pokemon.moves[action2[2]]
            print(f"[DEBUG] Player2's move: {move2.name} (Accuracy: {arc2})")
            self.fight(move2, player2.current_pokemon, player1.current_pokemon, player2, arc2)
            if action2[1].moves[action2[2]].name == 'Transform':
                print("[DEBUG] Player2 used Transform.")
                self.player2.current_pokemon.moves = self.player2.opponent.current_pokemon.moves
                self.pokemon_images[self.player2.current_pokemon.name] = self.pokemon_images[self.player2.opponent.current_pokemon.name]
            faint1 = self.check_fainting(player1.current_pokemon)
            faint2 = self.check_fainting(player2.current_pokemon)
            print(f"[DEBUG] Faint check: player1={faint1}, player2={faint2}")
            if faint1 and faint2:
                print("[DEBUG] Both Pokémon fainted.")
                self.fainted_pokemon.append(player2.current_pokemon.name)
                self.fainted_pokemon.append(player1.current_pokemon.name)
                player1.remaining_pokemons -= 1
                player2.remaining_pokemons -= 1
                return [player1.name, player2.name]
            if faint1:
                print(f"[DEBUG] {player1.current_pokemon.name} fainted.")
                self.fainted_pokemon.append(player1.current_pokemon.name)
                player1.remaining_pokemons -= 1
                return [player1.name]
            if faint2:
                print(f"[DEBUG] {player2.current_pokemon.name} fainted.")
                self.fainted_pokemon.append(player2.current_pokemon.name)
                player2.remaining_pokemons -= 1
                return [player2.name]
        elif len(action2) < 1:
            print("[DEBUG] Player2 is resting. Player1 is attacking.")
            move1 = player1.current_pokemon.moves[action1[2]]
            print(f"[DEBUG] Player1's move: {move1.name} (Accuracy: {arc1})")
            self.fight(move1, player1.current_pokemon, player2.current_pokemon, player1, arc1)
            if action1[1].moves[action1[2]].name == 'Transform':
                print("[DEBUG] Player1 used Transform.")
                self.player1.current_pokemon.moves = self.player1.opponent.current_pokemon.moves
                self.pokemon_images[self.player1.current_pokemon.name] = self.pokemon_images[self.player1.opponent.current_pokemon.name]
            faint1 = self.check_fainting(player1.current_pokemon)
            faint2 = self.check_fainting(player2.current_pokemon)
            print(f"[DEBUG] Faint check: player1={faint1}, player2={faint2}")
            if faint1 and faint2:
                print("[DEBUG] Both Pokémon fainted.")
                self.fainted_pokemon.append(player1.current_pokemon.name)
                self.fainted_pokemon.append(player2.current_pokemon.name)
                player1.remaining_pokemons -= 1
                player2.remaining_pokemons -= 1
                return [player1.name, player2.name]
            if faint1:
                print(f"[DEBUG] {player1.current_pokemon.name} fainted.")
                self.fainted_pokemon.append(player1.current_pokemon.name)
                player1.remaining_pokemons -= 1
                return [player1.name]
            if faint2:
                print(f"[DEBUG] {player2.current_pokemon.name} fainted.")
                self.fainted_pokemon.append(player2.current_pokemon.name)
                player2.remaining_pokemons -= 1
                return [player2.name]
        print("[DEBUG] Exiting handle_rest_fight() with no fainting.")

    
    def handle_switch_fight(self, player1, action1, player2, action2,arc1,arc2):
        if action1[0] == 'switch':
            self.switch(player1, action1[2])
            self.draw_middle_area(self.player1.current_pokemon, self.player2.current_pokemon)
            pygame.display.update()
            move2 = player2.current_pokemon.moves[action2[2]]
            self.fight(move2, player2.current_pokemon, player1.current_pokemon,player2,arc2)
            if action2[1].moves[action2[2]].name == 'Transform':
                self.player2.current_pokemon.moves=self.player2.opponent.current_pokemon.moves
                self.pokemon_images[self.player2.current_pokemon.name] = self.pokemon_images[self.player2.opponent.current_pokemon.name]
            if self.check_fainting(player2.current_pokemon) and self.check_fainting(player1.current_pokemon):
                self.fainted_pokemon.append(player2.current_pokemon.name)
                self.fainted_pokemon.append(player1.current_pokemon.name)
                player1.remaining_pokemons -= 1
                player2.remaining_pokemons -= 1
                return [player1.name, player2.name]
            if self.check_fainting(player1.current_pokemon):
                self.fainted_pokemon.append(player1.current_pokemon.name)
                player1.remaining_pokemons -= 1
                return [player1.name]
            if self.check_fainting(player2.current_pokemon):
                self.fainted_pokemon.append(player2.current_pokemon.name)
                player2.remaining_pokemons -= 1
                return [player2.name]
        elif action2[0] == 'switch':
            self.switch(player2, action2[2])
            self.draw_middle_area(self.player1.current_pokemon, self.player2.current_pokemon)
            pygame.display.update()
            move1 = player1.current_pokemon.moves[action1[2]]
            self.fight(move1, player1.current_pokemon, player2.current_pokemon,player1,arc1)
            if action1[1].moves[action1[2]].name == 'Transform':
                self.player1.current_pokemon.moves=self.player1.opponent.current_pokemon.moves
                self.pokemon_images[self.player1.current_pokemon.name] = self.pokemon_images[self.player1.opponent.current_pokemon.name]
            if self.check_fainting(player1.current_pokemon) and self.check_fainting(player2.current_pokemon):
                self.fainted_pokemon.append(player1.current_pokemon.name)
                self.fainted_pokemon.append(player2.current_pokemon.name)
                player1.remaining_pokemons -= 1
                player2.remaining_pokemons -= 1
                return [player1.name, player2.name]
            if self.check_fainting(player1.current_pokemon):
                self.fainted_pokemon.append(player1.current_pokemon.name)
                player1.remaining_pokemons -= 1
                return [player1.name]
            if self.check_fainting(player2.current_pokemon):
                self.fainted_pokemon.append(player2.current_pokemon.name)
                player2.remaining_pokemons -= 1
                return [player2.name]

    def prompt_player_command(self, player, valid_commands):
        command = None
        while command not in valid_commands:
            self.battle_message = f"{player.name}'s Move"
            self.draw_battle_message(0)
            self.draw_bottom_buttons(valid_commands)
            waiting = True
            while waiting:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.quit_game()
                    action = self.get_button_click(event)
                    if action in valid_commands:
                        command = action
                        self.battle_message = f"{player.name} chose: {command}"
                        self.draw_battle_message(0)
                        waiting = False
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
        while not self.gameOver:
            PreparedFlag1 = False
            PreparedFlag2 = False
            print(f"[DEBUG] PreparedFlag1 = {PreparedFlag1},PreparedFlag2 = {PreparedFlag2}")
            print(f"[DEBUG] Starting turn {turn}")
            arc1 = None
            arc2 = None
            self.screen.fill((0, 0, 0))
            valid_commands = ['fight', 'switch', 'list', 'exit']
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
                    for event in pygame.event.get():
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
                    self.gameOver = True
                    break
                if(action1 and action1[1] is not None and not isinstance(action1[1], int)):
                    print(f"[DEBUG] Storing last_move_used: {action1[1].moves[action1[2]].name}")
                    self.player1.current_pokemon.last_move_used = action1[1].moves[action1[2]].name
                if self.player1.current_pokemon.last_move_used == 'Sketch':
                    print("[DEBUG] Player1 used Sketch. Searching for opponent’s last move.")
                    for i in range(len(self.move_log_stack) - 1, -1, -1):
                        entry = self.move_log_stack[i]
                        if entry.startswith(f"{self.player1.current_pokemon.name} used Sketch"):
                            if i > 0:
                                prev_entry = self.move_log_stack[i - 1]
                                if prev_entry.startswith(f"{self.player2.current_pokemon.name} used "):
                                    move_name = prev_entry.split(" used ")[1].strip()
                                    print(f"[DEBUG] Sketch will copy move: {move_name}")
                                    for j, n in enumerate(self.player2.current_pokemon.moves):
                                        if n.name.lower() == move_name.lower():
                                            for k, m in enumerate(self.player1.current_pokemon.moves):
                                                if m.name.lower() == 'sketch':
                                                    self.player1.current_pokemon.moves[k] = self.player2.current_pokemon.moves[j]
                                                    self.battle_message = f"{self.player1.current_pokemon.name} learned {move_name}!"
                                                    self.draw_battle_message(1.3)
                                                    print(f"[DEBUG] {self.battle_message}")
                                                    self.battle_message = ""
                                                    self.draw_battle_message(0)
                                                    break
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
                        command = self.prompt_player_command(self.player2, valid_commands)
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
                            self.gameOver = True
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
                if (action2 and len(action2) > 1 and action2[1] and not isinstance(action2[1], int)
                    and effective_action1 and len(effective_action1) > 1 and effective_action1[1] and not isinstance(effective_action1[1], int)):
                    print("[DEBUG] Both moves are fight-type and not switching. Checking speed tie...")
                    if effective_action1[1].speed == action2[1].speed:
                        print("[DEBUG] Speed tie detected.")
                        if self.settings['is_host']:
                            print("[DEBUG] Host wins speed tie. Buffing host speed.")
                            for p in self.player1.pokemons:
                                if p.name == effective_action1[1].name:
                                    p.speed += 10
                                    print(f"[DEBUG] Boosted speed of {p.name} to {p.speed}")
                                    break
                        else:
                            print("[DEBUG] Host wins speed tie. Buffing host speed.")
                            for p in self.player2.pokemons:
                                if p.name == effective_action1[1].name:
                                    p.speed += 10
                                    print(f"[DEBUG] Boosted speed of {p.name} to {p.speed}")
                                    break
                if(action2 and len(action2) > 1 and action2[1] is not None and not isinstance(action2[1], int)):
                    print(f"[DEBUG] Storing last_move_used for Player2: {action2[1].moves[action2[2]].name}")
                    self.player2.current_pokemon.last_move_used = action2[1].moves[action2[2]].name
                if self.player2.current_pokemon.last_move_used == 'Sketch':
                    print("[DEBUG] Player2 used Sketch. Attempting to learn last move from Player1...")
                    for i in range(len(self.move_log_stack) - 1, -1, -1):
                        entry = self.move_log_stack[i]
                        if entry.startswith(f"{self.player2.current_pokemon.name} used Sketch"):
                            if i > 0:
                                prev_entry = self.move_log_stack[i - 1]
                                print(f"[DEBUG] Previous move found: {prev_entry}")
                                if prev_entry.startswith(f"{self.player1.current_pokemon.name} used "):
                                    move_name = prev_entry.split(" used ")[1].strip()
                                    print(f"[DEBUG] Player2 attempting to learn move: {move_name}")
                                    for j, n in enumerate(self.player1.current_pokemon.moves):
                                        if n.name.lower() == move_name.lower():
                                            for k, m in enumerate(self.player2.current_pokemon.moves):
                                                if m.name.lower() == 'sketch':
                                                    print(f"[DEBUG] Replacing Sketch with {move_name} at index {k}")
                                                    self.player2.current_pokemon.moves[k] = self.player1.current_pokemon.moves[j]
                                                    self.battle_message = f"{self.player2.current_pokemon.name} learned {move_name}!"
                                                    self.draw_battle_message(1.3)
                                                    self.battle_message = ""
                                                    self.draw_battle_message(0)
                                                    print(f"[DEBUG] {self.battle_message}")
                                                    break
                            break
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
                    if move_name == 'Transform':
                        print("[DEBUG] Player1 used Transform.")
                        self.player1.current_pokemon.moves = self.player1.opponent.current_pokemon.moves
                        self.pokemon_images[self.player1.current_pokemon.name] = self.pokemon_images[self.player1.opponent.current_pokemon.name]
                if action2 and len(action2) > 0 and hasattr(action2[1], "moves"):
                    move_name = action2[1].moves[action2[2]].name
                    print(f"[DEBUG] Player2 used move: {move_name}")
                    if move_name == 'Transform':
                        print("[DEBUG] Player2 used Transform.")
                        self.player2.current_pokemon.moves = self.player2.opponent.current_pokemon.moves
                        self.pokemon_images[self.player2.current_pokemon.name] = self.pokemon_images[self.player2.opponent.current_pokemon.name]
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
                    if move_name == 'Transform':
                        print("[DEBUG] Player1 used Transform.")
                        self.player1.current_pokemon.moves = self.player1.opponent.current_pokemon.moves
                        self.pokemon_images[self.player1.current_pokemon.name] = self.pokemon_images[self.player1.opponent.current_pokemon.name]
                if action2 and hasattr(action2[1], "moves"):
                    move_name = action2[1].moves[action2[2]].name
                    print(f"[DEBUG] Player2 used move: {move_name}")
                    if move_name == 'Transform':
                        print("[DEBUG] Player2 used Transform.")
                        self.player2.current_pokemon.moves = self.player2.opponent.current_pokemon.moves
                        self.pokemon_images[self.player2.current_pokemon.name] = self.pokemon_images[self.player2.opponent.current_pokemon.name]
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