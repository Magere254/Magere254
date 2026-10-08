

import random
import tkinter as tk

WIDTH = 600
HEIGHT = 400
GRAVITY = 0.4       # how much faster a ball falls each frame
BOUNCINESS = 0.85   # 1.0 = never loses energy, 0.5 = loses half each bounce
DELAY_MS = 16       # wait ~16 ms between frames (about 60 frames per second)


class Ball:
    """One ball: knows its position, speed, size, and how to move itself."""

    def __init__(self, canvas, x, y):
        self.canvas = canvas
        self.radius = random.randint(10, 30)
        self.dx = random.uniform(-4, 4)   # horizontal speed
        self.dy = random.uniform(-4, 0)   # vertical speed (negative = up)

        color = random.choice(["red", "orange", "gold", "green",
                               "deepskyblue", "violet", "pink"])

        # Draw the ball as a circle and remember its id so we can move it later
        self.id = canvas.create_oval(
            x - self.radius, y - self.radius,
            x + self.radius, y + self.radius,
            fill=color, outline="white"
        )

    def move(self):
        """Update the ball's speed, move it, and bounce off the walls."""
        self.dy += GRAVITY  # gravity pulls the ball down a little more each frame
        self.canvas.move(self.id, self.dx, self.dy)

        # Find out where the ball is now: left, top, right, bottom edges
        left, top, right, bottom = self.canvas.coords(self.id)

        # Hit the floor: flip vertical direction and lose a bit of energy
        if bottom >= HEIGHT:
            self.canvas.move(self.id, 0, HEIGHT - bottom)  # put it back on the floor
            self.dy = -self.dy * BOUNCINESS

        # Hit the ceiling
        if top <= 0:
            self.canvas.move(self.id, 0, -top)
            self.dy = -self.dy

        # Hit the left or right wall: flip horizontal direction
        if left <= 0:
            self.canvas.move(self.id, -left, 0)
            self.dx = -self.dx
        elif right >= WIDTH:
            self.canvas.move(self.id, WIDTH - right, 0)
            self.dx = -self.dx


def main():
    window = tk.Tk()
    window.title("Bouncing Balls")

    canvas = tk.Canvas(window, width=WIDTH, height=HEIGHT, bg="#1a1a2e")
    canvas.pack()


    canvas.create_text(WIDTH // 2, 20, fill="white",
                       text="Click anywhere to add a ball")

    balls = [Ball(canvas, random.randint(50, WIDTH - 50), 50) for _ in range(3)]

    def add_ball(event):
        """Runs every time you click; event.x and event.y are the mouse position."""
        balls.append(Ball(canvas, event.x, event.y))

    canvas.bind("<Button-1>", add_ball)  # connect left-click to add_ball

    def animate():
        """Move every ball one step, then schedule the next frame."""
        for ball in balls:
            ball.move()
        window.after(DELAY_MS, animate)

    animate()
    window.mainloop()


if __name__ == "__main__":
    main()