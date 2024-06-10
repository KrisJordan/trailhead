import {
    forward,
    backward,
    left,
    right,
    moveTo,
    turnTo,
    setSpeed,
    setOnClick
} from "introcs/turtle";

import { executeCode } from "./bridge";

interface Message {
    commands: Command[];
}

type Command = AmountCommand | CoordinateCommand;

type AmountCommand = {
    type: 'forward' | 'backward' | 'left' | 'right' | 'turnTo' | 'setSpeed';
    amount: number;
};

type CoordinateCommand = {
    type: 'moveTo';
    x: number;
    y: number;
};

const main = () => {
    executeCode<Message>("main()").then(draw);
};

const draw = (data: Message) => {
    data.commands.forEach(command => {
        switch (command.type) {
            case 'forward':
                forward(command.amount);
                break;
            case 'backward':
                backward(command.amount);
                break;
            case 'left':
                left(command.amount);
                break;
            case 'right':
                right(command.amount);
                break;
            case 'turnTo':
                turnTo(command.amount);
                break;
            case 'setSpeed':
                setSpeed(command.amount);
                break;
            case 'moveTo':
                moveTo(command.x, command.y);
                break;
        }
    })
};

const onClick = (x: number, y: number) => {
    executeCode<Message>(`click(${x}, ${y})`).then(draw);
};

setOnClick(onClick);
addEventListener("load", main);