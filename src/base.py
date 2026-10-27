def get_online_role_from_click(pos, host_button, join_button):
    if host_button.is_clicked(pos):
        return True
    if join_button.is_clicked(pos):
        return False
    return None


def run_ui_setup():
    import pygame
    from src.online_setup import online_setup # type: ignore
    
    pygame.init()
    WIDTH, HEIGHT = 1300, 650
    #WIDTH, HEIGHT = 800, 600
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Pokémon Battle Setup")
    WHITE = (255, 255, 255)
    BLACK = (0, 0, 0)
    GRAY = (200, 200, 200)
    BLUE = (0, 120, 215)
    DARK_GRAY = (100, 100, 100)
    RED = (255, 0, 0)
    FONT_LARGE = pygame.font.SysFont("arial", 48)
    FONT_MED = pygame.font.SysFont("arial", 32)
    FONT_SMALL = pygame.font.SysFont("arial", 24)
    state = "welcome_animation"
    input_text = ""
    error_message = ""
    player_name_phase = 1
    dropdown = None
    game_details = {
        "mode": None,
        "player1_name": "",
        "player2_name": "",
        "generation": None,
        "party_size": None,
        "move_size": None,
        "is_host": None,   
        "host_ip": None,   
        "conn": None       
    }
    class Button:
        def __init__(self, text, pos, size=(300, 60)):
            self.text = text
            self.rect = pygame.Rect(pos, size)

        def draw(self, surface, color=BLUE):
            pygame.draw.rect(surface, color, self.rect, border_radius=8)
            text_surface = FONT_MED.render(self.text, True, WHITE)
            surface.blit(text_surface, text_surface.get_rect(center=self.rect.center))

        def is_clicked(self, pos):
            return self.rect.collidepoint(pos)

    class Dropdown:
        def __init__(self, label, options, pos):
            self.label = label
            self.options = options
            self.rect = pygame.Rect(pos, (200, 40))
            self.active = False
            self.selected = None

        def draw(self, surface):
            pygame.draw.rect(surface, GRAY, self.rect, border_radius=6)
            label_surface = FONT_SMALL.render(f"{self.label}: {self.selected if self.selected else 'Select'}", True, BLACK)
            surface.blit(label_surface, label_surface.get_rect(midleft=(self.rect.x + 10, self.rect.centery)))
            if self.active:
                mouse_pos = pygame.mouse.get_pos()
                for i, option in enumerate(self.options):
                    opt_rect = pygame.Rect(self.rect.x, self.rect.y + 40 * (i + 1), 200, 40)
                    is_hovered = opt_rect.collidepoint(mouse_pos)
                    pygame.draw.rect(surface, (150, 150, 150) if is_hovered else DARK_GRAY, opt_rect, border_radius=6)
                    opt_surface = FONT_SMALL.render(str(option), True, WHITE)
                    surface.blit(opt_surface, opt_surface.get_rect(center=opt_rect.center))

        def handle_event(self, event):
            if event.type == pygame.MOUSEBUTTONDOWN:
                if self.rect.collidepoint(event.pos):
                    self.active = not self.active
                elif self.active:
                    for i, option in enumerate(self.options):
                        opt_rect = pygame.Rect(self.rect.x, self.rect.y + 40 * (i + 1), 200, 40)
                        if opt_rect.collidepoint(event.pos):
                            self.selected = option
                            self.active = False
                            return option
                    self.active = False
            return None

    pvc_button = Button("Player vs Computer", (WIDTH // 2 - 150, HEIGHT // 2 - 80))
    pvp_button = Button("Player vs Player", (WIDTH // 2 - 150, HEIGHT // 2 + 20))
    online_button = Button("Online Mode", (WIDTH // 2 - 150, HEIGHT // 2 + 120))
    next_button = Button("Next", (WIDTH // 2 - 75, HEIGHT // 2 + 150), (150, 50))
    host_button = Button("Host Game", (WIDTH // 2 - 150, HEIGHT // 2 - 20))
    join_button = Button("Join Game", (WIDTH // 2 - 150, HEIGHT // 2 + 60))
    
    
    def draw_centered_text(text, y, font, color=WHITE):
        surface = font.render(text, True, color)
        rect = surface.get_rect(center=(WIDTH // 2, y))
        screen.blit(surface, rect)

    def fade_out(surface, speed=10):
        fade = pygame.Surface((WIDTH, HEIGHT))
        fade.fill(BLACK)
        for alpha in range(0, 255, speed):
            fade.set_alpha(alpha)
            surface.blit(fade, (0, 0))
            pygame.display.update()
            pygame.time.delay(30)
            
    pokeball_radius = 120
    center_circle_radius = 25
    border_thickness = 5
    white_border_thickness = 2
    animation_progress = 0
    text_alpha = 0
    animation_speed = 0.15
    exit_animation = False
    welcome_text = "Welcome to Pokémon Battle!"
    welcome_text_surface = FONT_LARGE.render(welcome_text, True, WHITE)
    welcome_text_rect = welcome_text_surface.get_rect(center=(WIDTH // 2, HEIGHT // 2))
    animation_delay = 0 
    
    running = True
    while running:
        screen.fill(BLACK)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit
            if (event.type == pygame.MOUSEBUTTONDOWN
                    and getattr(event, "button", 0) in (4, 5)):
                continue

            if state == "select_mode":
                if event.type == pygame.MOUSEBUTTONDOWN:
                    if pvc_button.is_clicked(event.pos):
                        game_details["mode"] = "PvC"
                        state = "input_names"
                    elif pvp_button.is_clicked(event.pos):
                        game_details["mode"] = "PvP"
                        state = "input_names"
                    elif online_button.is_clicked(event.pos):
                        game_details["mode"] = "Online"
                        state = "online_setup"

            elif state == "online_setup":
                if event.type == pygame.MOUSEBUTTONDOWN:
                    host = get_online_role_from_click(event.pos, host_button, join_button)
                    if host is not None:
                        game_details['is_host'] = host
                        input_text = ""
                        error_message = ""
                        try:
                            game_details["conn"] = online_setup(screen, host)
                        except (OSError, ValueError) as exc:
                            error_message = f"Could not set up online play: {exc}"
                        else:
                            state = "input_names"
                            if host:
                                player_name_phase = 1

            elif state == "input_names":
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_BACKSPACE:
                        input_text = input_text[:-1]
                    elif event.key == pygame.K_RETURN:
                        name = input_text.strip() or ("Host" if game_details["is_host"] else "Client")
                        input_text = ""
                        error_message = ""
                        if game_details["mode"] == "PvC":
                            game_details["player1_name"] = name
                            game_details["player2_name"] = "RED"
                            state = "select_generation"
                        elif game_details["mode"] == "PvP":
                            if player_name_phase == 1:
                                game_details["player1_name"] = name
                                player_name_phase = 2
                            else:
                                if name == game_details["player1_name"]:
                                    error_message = "Name already taken!"
                                else:
                                    game_details["player2_name"] = name
                                    error_message = ""
                                    state = "select_generation"
                        elif game_details["mode"] == "Online":
                            game_details["player1_name"] = name
                            state = "select_generation"
                    else:
                        if len(input_text) < 16:
                            input_text += event.unicode

                elif event.type == pygame.MOUSEBUTTONDOWN and next_button.is_clicked(event.pos):
                    name = input_text.strip() or ("Host" if game_details["is_host"] else "Client")
                    input_text = ""
                    error_message = ""
                    if game_details["mode"] == "PvC":
                        game_details["player1_name"] = name
                        game_details["player2_name"] = "RED"
                        state = "select_generation"
                    elif game_details["mode"] == "PvP":
                        if player_name_phase == 1:
                            game_details["player1_name"] = name
                            player_name_phase = 2
                        else:
                            if name == game_details["player1_name"]:
                               error_message = "Name already taken!"
                            else:
                                game_details["player2_name"] = name
                                state = "select_generation"
                    elif game_details["mode"] == "Online":
                        game_details["player1_name"] = name
                        state = "select_generation"


            elif state in ["select_generation", "select_party", "select_moves"]:
                result = dropdown.handle_event(event)
                if result is not None:
                    if state == "select_generation":
                        game_details["generation"] = result
                        state = "select_party"
                        dropdown = Dropdown("Party Size", list(range(1, 7)), (WIDTH // 2 - 100, 120))
                    elif state == "select_party":
                        game_details["party_size"] = result
                        state = "select_moves"
                        dropdown = Dropdown("Move Size", list(range(1, 11)), (WIDTH // 2 - 100, 120))
                    elif state == "select_moves":
                        game_details["move_size"] = result
                        state = "summary"

        if state == "welcome_animation":
            if not exit_animation:
                if animation_progress < 100:
                    animation_progress += animation_speed
                elif text_alpha < 255:
                    text_alpha += animation_speed * 2.5
                elif animation_delay < 60:
                    animation_delay += 1
                else:
                    exit_animation = True
                    text_alpha = 255
                    animation_delay = 0  
            else:
                if text_alpha > 0:
                    text_alpha -= animation_speed * 2.5
                elif animation_progress < 200:
                    animation_progress += animation_speed
                else:
                    fade_out(screen)
                    state = "select_mode"
                    
            if animation_progress <= 100:
                top_offset = -pokeball_radius + (animation_progress / 100.0) * (HEIGHT // 2 - welcome_text_rect.height // 2 - 20)
                bottom_offset = HEIGHT + pokeball_radius - (animation_progress / 100.0) * (HEIGHT // 2 - welcome_text_rect.height // 2 - 20)
            else:
                progress = animation_progress - 100
                top_offset = (HEIGHT // 2 - welcome_text_rect.height // 2 - 20) - (progress / 100.0) * (HEIGHT // 2 + pokeball_radius)
                bottom_offset = (HEIGHT // 2 + welcome_text_rect.height // 2 + 20) + (progress / 100.0) * (HEIGHT // 2 + pokeball_radius)
            
            pygame.draw.arc(screen, WHITE, 
                           [WIDTH // 2 - pokeball_radius - white_border_thickness, 
                            top_offset - pokeball_radius - white_border_thickness,
                            2 * (pokeball_radius + white_border_thickness), 
                            2 * (pokeball_radius + white_border_thickness)], 
                           0, 3.14159, white_border_thickness)
            
            pygame.draw.arc(screen, BLACK, 
                           [WIDTH // 2 - pokeball_radius - border_thickness, 
                            top_offset - pokeball_radius - border_thickness,
                            2 * (pokeball_radius + border_thickness), 
                            2 * (pokeball_radius + border_thickness)], 
                           0, 3.14159, border_thickness)
            
            pygame.draw.arc(screen, RED, 
                           [WIDTH // 2 - pokeball_radius, 
                            top_offset - pokeball_radius,
                            2 * pokeball_radius, 
                            2 * pokeball_radius], 
                           0, 3.14159, pokeball_radius)
            
            pygame.draw.arc(screen, BLACK, 
                           [WIDTH // 2 - center_circle_radius - border_thickness, 
                            top_offset - center_circle_radius - border_thickness,
                            2 * (center_circle_radius + border_thickness), 
                            2 * (center_circle_radius + border_thickness)], 
                           0, 3.14159, border_thickness)
            
            pygame.draw.arc(screen, WHITE, 
                           [WIDTH // 2 - center_circle_radius, 
                            top_offset - center_circle_radius,
                            2 * center_circle_radius, 
                            2 * center_circle_radius], 
                           0, 3.14159, center_circle_radius)
            
            pygame.draw.arc(screen, WHITE, 
                           [WIDTH // 2 - pokeball_radius - white_border_thickness, 
                            bottom_offset - pokeball_radius - white_border_thickness,
                            2 * (pokeball_radius + white_border_thickness), 
                            2 * (pokeball_radius + white_border_thickness)], 
                           3.14159, 6.28318, white_border_thickness)
            
            pygame.draw.arc(screen, BLACK, 
                           [WIDTH // 2 - pokeball_radius - border_thickness, 
                            bottom_offset - pokeball_radius - border_thickness,
                            2 * (pokeball_radius + border_thickness), 
                            2 * (pokeball_radius + border_thickness)], 
                           3.14159, 6.28318, border_thickness)
            
            pygame.draw.arc(screen, WHITE, 
                           [WIDTH // 2 - pokeball_radius, 
                            bottom_offset - pokeball_radius,
                            2 * pokeball_radius, 
                            2 * pokeball_radius], 
                           3.14159, 6.28318, pokeball_radius)
            
            pygame.draw.arc(screen, BLACK, 
                           [WIDTH // 2 - center_circle_radius - border_thickness, 
                            bottom_offset - center_circle_radius - border_thickness,
                            2 * (center_circle_radius + border_thickness), 
                            2 * (center_circle_radius + border_thickness)], 
                           3.14159, 6.28318, border_thickness)
            
            pygame.draw.arc(screen, WHITE, 
                           [WIDTH // 2 - center_circle_radius, 
                            bottom_offset - center_circle_radius,
                            2 * center_circle_radius, 
                            2 * center_circle_radius], 
                           3.14159, 6.28318, center_circle_radius)
            
            if 0 < text_alpha <= 255:
                text_surface_with_alpha = welcome_text_surface.copy()
                text_surface_with_alpha.set_alpha(text_alpha)
                screen.blit(text_surface_with_alpha, welcome_text_rect)

        elif state == "select_mode":
            draw_centered_text("Select Game Mode", 100, FONT_LARGE)
            pvc_button.draw(screen)
            pvp_button.draw(screen)
            online_button.draw(screen)

        elif state == "online_setup":
            draw_centered_text("Online Mode Setup", 80, FONT_LARGE)
            host_button.draw(screen)
            join_button.draw(screen)

        elif state == "input_names":
            name_label = "Enter your name"
            if game_details["mode"] == "PvP" and player_name_phase == 2:
                name_label = "Enter name for Player 2"
            draw_centered_text(name_label, 100, FONT_LARGE)
            input_box = pygame.Rect(WIDTH // 2 - 150, HEIGHT // 2 - 25, 300, 50)
            pygame.draw.rect(screen, GRAY, input_box, border_radius=10)
            name_surface = FONT_MED.render(input_text + "|", True, BLACK)
            screen.blit(name_surface, name_surface.get_rect(center=input_box.center))
            next_button.draw(screen)
            if error_message:
                error_surface = FONT_SMALL.render(error_message, True, RED)
                screen.blit(error_surface, (WIDTH // 2 - error_surface.get_width() // 2, HEIGHT // 2 + 40))


        elif state == "select_generation":
            if not dropdown:
                dropdown = Dropdown("Generation", list(range(1, 10)) + ["ALL"], (WIDTH // 2 - 100, 120))
            draw_centered_text("Select Generation", 60, FONT_LARGE)
            dropdown.draw(screen)

        elif state == "select_party":
            draw_centered_text("Select Party Size", 60, FONT_LARGE)
            dropdown.draw(screen)

        elif state == "select_moves":
            draw_centered_text("Select Move Size", 60, FONT_LARGE)
            dropdown.draw(screen)

        elif state == "summary":
            draw_centered_text("Summary", 60, FONT_LARGE)
            draw_centered_text(f"Mode: {game_details['mode']}", 140, FONT_MED)
            draw_centered_text(f"Player 1: {game_details['player1_name']}", 200, FONT_MED)
            if game_details["player2_name"]:
                draw_centered_text(f"Player 2: {game_details['player2_name']}", 260, FONT_MED)
            draw_centered_text(f"Generation: {game_details['generation']}", 320, FONT_MED)
            draw_centered_text(f"Party Size: {game_details['party_size']}", 380, FONT_MED)
            draw_centered_text(f"Move Size: {game_details['move_size']}", 440, FONT_MED)
            pygame.display.update()
            pygame.time.delay(1500)
            state = "done"

        elif state == "done":
            screen.fill(BLACK)
            pygame.display.update()
            running = False
        pygame.display.update()
        
    return screen,game_details
