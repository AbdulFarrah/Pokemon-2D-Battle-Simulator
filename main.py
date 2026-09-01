from src.game import Game  # type: ignore
from src.game import ConnectionLost  # type: ignore
from src.base import run_ui_setup  # type: ignore
from src.restart import show_restart_prompt  # type: ignore
import pygame


if __name__ == '__main__':
    pygame.init()
    while True:
        screen, settings = run_ui_setup()
        conn = settings.get("conn")
        game = Game(settings, screen)
        try:
            game.game_loop()
            if conn:
                conn.close()
            if not show_restart_prompt(screen):
                break
        except ConnectionLost:
            if conn:
                conn.close()
            if not show_restart_prompt(screen):
                break
            
            