/**
 * Color represents a single, digital color made up of 3 component 
 * color properties:
 * 
 * - red
 * - green
 * - blue
 * 
 * Note: You should not modify this file.
 */
export class Color {

    red: number;
    green: number;
    blue: number;

    constructor(red: number, green: number, blue: number) {
        this.red = red;
        this.green = green;
        this.blue = blue;
    }

    /**
     * The copy method is used to construct and initialize a new Color
     * object that is a copy of the Color object the method is called on.
     */
    copy = (): Color => {
        return new Color(this.red, this.green, this.blue);
    }
    
}