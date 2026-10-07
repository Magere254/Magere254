import random
import tkinter as tk

CELL = 25
COLS = 24
ROWS = 18
DELAY = 120


class SnakeGame:
    def __init__(self, window):
        self.window = window
        window.title("Snake")

        self.canvas = tk.Canvas(
            window, width=COLS * CELL, height=ROWS * CELL, bg="#1a1a2e"
        )
        self.canvas.pack()

        window.bind("<Key>", self.on_key)

        self.reset()
        self.tick()

    def reset(self):
        self.snake = [(5, 9), (4, 9), (3, 9)]
        self.direction = (1, 0)
        self.next_direction = (1, 0)
        self.score = 0
        self.game_over = False
        self.place_food()

    def place_food(self):
        while True:
            food = (random.randint(0, COLS - 1), random.randint(0, ROWS - 1))
            if food not in self.snake:
                self.food = food
                return

    def on_key(self, event):
        key = event.keysym.lower()

        directions = {
            "up": (0, -1),    "w": (0, -1),
            "down": (0, 1),   "s": (0, 1),
            "left": (-1, 0),  "a": (-1, 0),
            "right": (1, 0),  "d": (1, 0),
        }

        if key in directions:
            new_dir = directions[key]
            opposite = (-self.direction[0], -self.direction[1])
            if new_dir != opposite:
                self.next_direction = new_dir
        elif key == "r" and self.game_over:
            self.reset()

    def update(self):
        self.direction = self.next_direction
        head_x, head_y = self.snake[0]
        dx, dy = self.direction
        new_head = (head_x + dx, head_y + dy)

        if not (0 <= new_head[0] < COLS and 0 <= new_head[1] < ROWS):
            self.game_over = True
            return

        if new_head in self.snake:
            self.game_over = True
            return

        self.snake.insert(0, new_head)

        if new_head == self.food:
            self.score += 1
            self.place_food()
        else:
            self.snake.pop()

    def draw(self):
        self.canvas.delete("all")

        fx, fy = self.food
        self.canvas.create_oval(
            fx * CELL + 3, fy * CELL + 3,
            (fx + 1) * CELL - 3, (fy + 1) * CELL - 3,
            fill="red", outline=""
        )

        for i, (x, y) in enumerate(self.snake):
            color = "#7CFC00" if i == 0 else "#2e8b57"
            self.canvas.create_rectangle(
                x * CELL + 1, y * CELL + 1,
                (x + 1) * CELL - 1, (y + 1) * CELL - 1,
                fill=color, outline=""
            )

        self.canvas.create_text(
            50, 15, text=f"Score: {self.score}", fill="white",
            font=("Arial", 14, "bold")
        )

        if self.game_over:
            self.canvas.create_text(
                COLS * CELL // 2, ROWS * CELL // 2 - 15,
                text="GAME OVER", fill="white", font=("Arial", 32, "bold")
            )
            self.canvas.create_text(
                COLS * CELL // 2, ROWS * CELL // 2 + 25,
                text="Press R to restart", fill="lightgray", font=("Arial", 16)
            )

    def tick(self):
        if not self.game_over:
            self.update()
        self.draw()
        self.window.after(DELAY, self.tick)


def main():
    window = tk.Tk()
    SnakeGame(window)
    window.mainloop()


if __name__ == "__main__":
    main()