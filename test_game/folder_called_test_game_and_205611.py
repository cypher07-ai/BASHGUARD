import os
import random
import sys
import pygame

# Initialize Pygame
try:
    pygame.init()
    pygame.font.init()
except Exception as e:
    print(f"Failed to initialize pygame: {e}")
    sys.exit(1)

# Constants
SCREEN_WIDTH = 600
SCREEN_HEIGHT = 600
GRID_SIZE = 20
GRID_WIDTH = SCREEN_WIDTH // GRID_SIZE
GRID_HEIGHT = SCREEN_HEIGHT // GRID_SIZE
FPS = 10

# Colors (RGB)
BACKGROUND_COLOR = (15, 15, 20)
GRID_COLOR = (30, 30, 45)
SNAKE_HEAD_COLOR = (46, 204, 113)
SNAKE_BODY_COLOR = (39, 174, 96)
FOOD_COLOR = (231, 76, 60)
TEXT_COLOR = (245, 245, 245)
PANEL_COLOR = (25, 25, 35)

# Directions
UP = (0, -1)
DOWN = (0, 1)
LEFT = (-1, 0)
RIGHT = (1, 0)


class SnakeGame:
    def __init__(self):
        # Ensure the test_game directory exists
        os.makedirs("test_game", exist_ok=True)

        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("BashGuard Snake Arcade")
        self.clock = pygame.time.Clock()

        # Load fonts safely
        try:
            self.font_small = pygame.font.SysFont("Arial", 20)
            self.font_large = pygame.font.SysFont("Arial", 40, bold=True)
        except:
            self.font_small = pygame.font.Font(None, 24)
            self.font_large = pygame.font.Font(None, 48)

        self.reset_game()

    def reset_game(self):
        # Initialize snake in the center
        self.snake = [
            (GRID_WIDTH // 2, GRID_HEIGHT // 2),
            (GRID_WIDTH // 2, GRID_HEIGHT // 2 + 1),
            (GRID_WIDTH // 2, GRID_HEIGHT // 2 + 2),
        ]
        self.direction = UP
        self.next_direction = UP
        self.score = 0
        self.game_over = False
        self.spawn_food()

    def spawn_food(self):
        while True:
            self.food = (
                random.randint(0, GRID_WIDTH - 1),
                random.randint(0, GRID_HEIGHT - 1),
            )
            # Ensure food doesn't spawn on the snake
            if self.food not in self.snake:
                break

    def handle_input(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP or event.key == pygame.K_w:
                    if self.direction != DOWN:
                        self.next_direction = UP
                elif event.key == pygame.K_DOWN or event.key == pygame.K_s:
                    if self.direction != UP:
                        self.next_direction = DOWN
                elif event.key == pygame.K_LEFT or event.key == pygame.K_a:
                    if self.direction != RIGHT:
                        self.next_direction = LEFT
                elif event.key == pygame.K_RIGHT or event.key == pygame.K_d:
                    if self.direction != LEFT:
                        self.next_direction = RIGHT
                elif event.key == pygame.K_r and self.game_over:
                    self.reset_game()
                elif event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()

    def update(self):
        if self.game_over:
            return

        self.direction = self.next_direction
        head_x, head_y = self.snake[0]
        dir_x, dir_y = self.direction
        new_head = (head_x + dir_x, head_y + dir_y)

        # Check wall collisions
        if (
            new_head[0] < 0
            or new_head[0] >= GRID_WIDTH
            or new_head[1] < 0
            or new_head[1] >= GRID_HEIGHT
        ):
            self.game_over = True
            return

        # Check self collisions
        if new_head in self.snake:
            self.game_over = True
            return

        # Insert new head
        self.snake.insert(0, new_head)

        # Check food collision
        if new_head == self.food:
            self.score += 10
            self.spawn_food()
        else:
            # Remove tail if no food eaten
            self.snake.pop()

    def draw(self):
        self.screen.fill(BACKGROUND_COLOR)

        # Draw subtle grid lines
        for x in range(0, SCREEN_WIDTH, GRID_SIZE):
            pygame.draw.line(
                self.screen, GRID_COLOR, (x, 0), (x, SCREEN_HEIGHT), 1
            )
        for y in range(0, SCREEN_HEIGHT, GRID_SIZE):
            pygame.draw.line(
                self.screen, GRID_COLOR, (0, y), (SCREEN_WIDTH, y), 1
            )

        # Draw food with a glowing effect
        food_rect = pygame.Rect(
            self.food[0] * GRID_SIZE + 2,
            self.food[1] * GRID_SIZE + 2,
            GRID_SIZE - 4,
            GRID_SIZE - 4,
        )
        pygame.draw.ellipse(self.screen, FOOD_COLOR, food_rect)

        # Draw snake
        for i, segment in enumerate(self.snake):
            seg_rect = pygame.Rect(
                segment[0] * GRID_SIZE + 1,
                segment[1] * GRID_SIZE + 1,
                GRID_SIZE - 2,
                GRID_SIZE - 2,
            )
            color = SNAKE_HEAD_COLOR if i == 0 else SNAKE_BODY_COLOR
            pygame.draw.rect(self.screen, color, seg_rect, border_radius=4)

        # Draw Score Panel Header
        panel_rect = pygame.Rect(0, 0, SCREEN_WIDTH, 40)
        pygame.draw.rect(self.screen, PANEL_COLOR, panel_rect)
        pygame.draw.line(
            self.screen, GRID_COLOR, (0, 40), (SCREEN_WIDTH, 40), 2
        )

        score_surf = self.font_small.render(
            f"SCORE: {self.score}", True, TEXT_COLOR
        )
        self.screen.blit(score_surf, (20, 10))

        controls_surf = self.font_small.render(
            "WASD / ARROWS to Move", True, (150, 150, 170)
        )
        self.screen.blit(
            controls_surf,
            (SCREEN_WIDTH - controls_surf.get_width() - 20, 10),
        )

        # Game Over Overlay
        if self.game_over:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            overlay.set_alpha(180)
            overlay.fill((0, 0, 0))
            self.screen.blit(overlay, (0, 0))

            go_surf = self.font_large.render("GAME OVER", True, FOOD_COLOR)
            score_final = self.font_small.render(
                f"Final Score: {self.score}", True, TEXT_COLOR
            )
            restart_surf = self.font_small.render(
                "Press 'R' to Restart or 'ESC' to Quit", True, TEXT_COLOR
            )

            self.screen.blit(
                go_surf,
                (
                    SCREEN_WIDTH // 2 - go_surf.get_width() // 2,
                    SCREEN_HEIGHT // 2 - 50,
                ),
            )
            self.screen.blit(
                score_final,
                (
                    SCREEN_WIDTH // 2 - score_final.get_width() // 2,
                    SCREEN_HEIGHT // 2 + 5,
                ),
            )
            self.screen.blit(
                restart_surf,
                (
                    SCREEN_WIDTH // 2 - restart_surf.get_width() // 2,
                    SCREEN_HEIGHT // 2 + 45,
                ),
            )

        pygame.display.flip()

    def run(self):
        while True:
            self.handle_input()
            self.update()
            self.draw()
            self.clock.tick(FPS)


if __name__ == "__main__":
    game = SnakeGame()
    game.run()
