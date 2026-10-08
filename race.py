import turtle
import random

screen = turtle.Screen()
screen.setup(800, 600)
screen.title("Python Car Race")
screen.bgcolor("lightgreen")

track = turtle.Turtle()
track.hideturtle()
track.speed(0)

track.penup()
track.goto(-350, 250)
track.pendown()

track.color("white")
track.pensize(5)
track.forward(700)

track.penup()
track.goto(-350, -250)
track.pendown()
track.forward(700)

track.penup()
track.goto(300, -250)
track.pendown()
track.setheading(90)
track.forward(500)

car1 = turtle.Turtle()
car1.shape("square")
car1.color("red")
car1.shapesize(1, 2)
car1.penup()
car1.goto(-300, 100)

car2 = turtle.Turtle()
car2.shape("square")
car2.color("blue")
car2.shapesize(1, 2)
car2.penup()
car2.goto(-300, -100)

finish = 280

while car1.xcor() < finish and car2.xcor() < finish:
    car1.forward(random.randint(1, 10))
    car2.forward(random.randint(1, 10))

if car1.xcor() >= finish and car2.xcor() >= finish:
    winner = "It's a tie!"
elif car1.xcor() >= finish:
    winner = "Red car wins!"
else:
    winner = "Blue car wins!"

result = turtle.Turtle()
result.hideturtle()
result.penup()
result.goto(0, 0)
result.write(winner, align="center", font=("Arial", 28, "bold"))

turtle.done()