import { Color } from "./Color";
import { Image } from "./Image";
import { Filter } from "./Filter";

// TODO: Insert Honor Pledge Here

/**
 * The InvertFilter's process method is provided to you as an example for
 * some ideas on how to implement an image processing algorithm given an input
 * image. All of yours will also create a copy, iterate through each pixel
 * using a nested for loop, and modify each pixel by applying logic and/or
 * arithmetic to manipulate it.
 */
export class InvertFilter extends Filter {
    
    constructor() {
        super();
        this.name = "Invert";
        this.amount = 1.0;
    }

    process = (input: Image): Image => {
        // First we'll setup our output image by copying the input image.
        // We must make a copy of our input image, otherwise we'd overwrite the data
        // of our original Image each time this filter's process method is applied.
        let output: Image = input.copy();

        // We'll work our way through the image one pixel at a time
        for (let row: number = 0; row < output.height; row++) {
            for (let col: number = 0; col < output.width; col++) {

                // Get a reference to the Color at row, col and store it in the pixel local variable
                let pixel: Color = output.pixels[row][col];

                // Initialize some additional local variables to store the R, G, B values for easy access.
                let red: number = pixel.red;
                let green: number = pixel.green;
                let blue: number = pixel.blue;

                // The goal of this filter, when applied with an amount of 1.0 or 100%,
                // is for black to become white, red to become cyan, green to become
                // purple, blue to become yellow, etc. Coming in, we know our component
                // values *must* be between 0.0 and 1.0. Thus, we can "invert" a
                // component by subtracting it from 1.0:
                //
                // Original Formula Inverted
                // ======== ======= ========
                // 0.00 -> 1.0 - 0.00 -> 1.00
                // 0.25 -> 1.0 - 0.25 -> 0.75
                // 0.50 -> 1.0 - 0.50 -> 0.50
                // 0.75 -> 1.0 - 0.75 -> 0.25
                // 1.00 -> 1.0 - 1.00 -> 0.00
                let redInverted: number = 1.0 - red;
                let greenInverted: number = 1.0 - green;
                let blueInverted: number = 1.0 - blue;

                // This is Carolina. We're not making filters that are merely "on"
                // or "off" -- nope -- we're making filters that can be applied
                // with a variable amount between 0.0 and 1.0. QR credit FTW.
                //
                // For the invert filter, an `amount` of 0.0 means 0% inverted,
                // 0.5 means 50% inverted, and 1.0 means 100% inverted.
                //
                // The way we'll do this is first figure out how "far away" from our
                // inverted target each component component is via subtraction.
                // Then we'll take that distance and multiply it by the percentage
                // *amount* property of the filter.
                //
                // This will give us a delta we can add to our original color values.
                let redDelta: number = (redInverted - red) * this.amount;
                let greenDelta: number = (greenInverted - green) * this.amount;
                let blueDelta: number = (blueInverted - blue) * this.amount;

                // Finally, we'll add the delta to each original component value.
                // Since pixel is a reference to a Color object in the copied Image's
                // 2D array, changing its RGB components influences the copy. Thus, we
                // do not need to assign pixel back to output.pixels[row][col].
                pixel.red = red + redDelta;
                pixel.green = green + greenDelta;
                pixel.blue = blue + blueDelta;
            }
        }

        return output;
    }

}

export class BorderFilter extends Filter {

    color: Color;

    constructor() {
        super();
        this.name = "Border";
        this.color = new Color(0.482, 0.686, 0.831);
    }

    process = (input: Image): Image => {
        // TODO 2.1
        return input;
    }

}

export class BrightnessFilter extends Filter {
    
    constructor() {
        super();
        this.name = "Brightness";
        this.amount = 0.5;
    }

    process = (input: Image): Image => {
        // TODO 2.2
        return input;
    }

}

export class ColorizeFilter extends Filter {
    
    color: Color;

    constructor() {
        super();
        this.name = "Colorize";
        this.color = new Color(0.482, 0.686, 0.831);
    }

    process = (input: Image): Image => {
        // TODO 2.3
        return input;
    }

}

export class ContrastFilter extends Filter {
    
    constructor() {
        super();
        this.name = "Contrast";
        this.amount = 0.5;
    }

    process = (input: Image): Image => {
        // TODO 2.4
        return input;
    }

}

export class SaturationFilter extends Filter {
    
    constructor() {
        super();
        this.name = "Saturation";
        this.amount = 0.5;
    }

    process = (input: Image): Image => {
        // TODO 2.5
        return input;
    }

}