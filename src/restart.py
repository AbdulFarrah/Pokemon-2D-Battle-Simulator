import pygame
import sys

def show_restart_prompt(screen):
    SCREEN_WIDTH, SCREEN_HEIGHT = screen.get_size()
    font = pygame.font.SysFont(None, 48)
    button_font = pygame.font.SysFont(None, 36)
    clock = pygame.time.Clock()
    BG_COLOR = (0, 0, 0)
    TEXT_COLOR = (255, 255, 255)
    BUTTON_COLOR = (100, 100, 255)
    BUTTON_HOVER = (150, 150, 255)
    question = "Do you want to restart the game?"
    button_width, button_height = 150, 60
    yes_button = pygame.Rect(SCREEN_WIDTH//2 - 170, SCREEN_HEIGHT//2 + 40, button_width, button_height)
    no_button = pygame.Rect(SCREEN_WIDTH//2 + 20, SCREEN_HEIGHT//2 + 40, button_width, button_height)

    while True:
        screen.fill(BG_COLOR)
        text_surface = font.render(question, True, TEXT_COLOR)
        screen.blit(text_surface, ((SCREEN_WIDTH - text_surface.get_width()) // 2, SCREEN_HEIGHT//2 - 60))
        mouse_pos = pygame.mouse.get_pos()
        for rect, label in [(yes_button, "YES"), (no_button, "NO")]:
            color = BUTTON_HOVER if rect.collidepoint(mouse_pos) else BUTTON_COLOR
            pygame.draw.rect(screen, color, rect, border_radius=10)
            label_surface = button_font.render(label, True, TEXT_COLOR)
            screen.blit(label_surface, (
                rect.centerx - label_surface.get_width() // 2,
                rect.centery - label_surface.get_height() // 2
            ))
        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if yes_button.collidepoint(mouse_pos):
                    return True
                elif no_button.collidepoint(mouse_pos):
                    show_thank_you(screen)
                    pygame.quit()
                    sys.exit()
        clock.tick(60)

def show_thank_you(screen):
    SCREEN_WIDTH, SCREEN_HEIGHT = screen.get_size()
    font = pygame.font.SysFont(None, 48)
    screen.fill((0, 0, 0))
    text_surface = font.render("Thanks for playing!", True, (255, 255, 255))
    screen.blit(text_surface, ((SCREEN_WIDTH - text_surface.get_width()) // 2, SCREEN_HEIGHT // 2))
    pygame.display.flip()
    pygame.time.delay(2000)