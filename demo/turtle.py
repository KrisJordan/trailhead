from pydantic import BaseModel

__template__ = "https://24s.comp110.com/static/turtle"


class Command(BaseModel):
    type: str
    amount: float


class CoordinateCommand(Command):
    amount: float = 0.0
    x: float
    y: float


class Turtle(BaseModel):

    commands: list[Command] = []

    def forward(self, amount: float) -> None:
        self.commands.append(Command(type="forward", amount=amount))

    def backward(self, amount: float) -> None:
        self.commands.append(Command(type="backward", amount=amount))

    def left(self, angle: float) -> None:
        self.commands.append(Command(type="left", amount=angle))

    def right(self, angle: float) -> None:
        self.commands.append(Command(type="right", amount=angle))

    def turnTo(self, angle: float) -> None:
        self.commands.append(Command(type="turnTo", amount=angle))

    def setSpeed(self, speed: float) -> None:
        self.commands.append(Command(type="setSpeed", amount=speed))

    def moveTo(self, x: float, y: float) -> None:
        self.commands.append(CoordinateCommand(type="moveTo", x=x, y=y))


from math import pi

DEGREE: float = -pi / 180.0


def main() -> Turtle:
    t: Turtle = Turtle()
    t.setSpeed(1000)
    return t


def click(x: float, y: float) -> Turtle:
    t: Turtle = Turtle()
    t.moveTo(x, y)
    branch(t, y * 0.15, 90 * DEGREE)
    return t


from random import random


def between(low: float, high: float) -> float:
    return low + random() * (high - low)


def branch(t: Turtle, height: float, angle: float) -> None:
    t.turnTo(angle)
    t.forward(height)
    if height > 10:
        branch(
            t,
            height * between(0.7, 0.8),
            angle + between(25 * DEGREE, 35 * DEGREE),
        )
        branch(
            t,
            height * between(0.7, 0.8),
            angle - between(25 * DEGREE, 35 * DEGREE),
        )
    t.turnTo(angle + pi)
    t.forward(height)
