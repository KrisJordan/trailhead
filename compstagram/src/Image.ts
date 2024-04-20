import { Color } from "./Color";

/**
 * Image represents a digital image via a 2D array of Color "pixels".
 * Its 2D pixel array is organized using a row-major order.
 * 
 * Note: You should not modify this file.
 */
export class Image {

    pixels: Color[][];
    width: number;
    height: number;

    /**
     * The Image constructor initializes a new Image to be filled with
     * white pixels.
     * 
     * @param width the number of columns in the image
     * @param height the number of rows in the image
     */
    constructor(width: number, height: number) {
        this.width = width;
        this.height = height;
        this.pixels = [];
        for (let row: number = 0; row < height; row++) {
            this.pixels[row] = [];
            for (let col: number = 0; col < width; col++) {
                this.pixels[row][col] = new Color(1, 1, 1);
            }
        }
    }

    /**
     * The copy method is used to construct and initialize a new Image
     * object that is a copy of the Image object the method is called on.
     */
    copy = (): Image => {
        let clone: Image = new Image(this.width, this.height);
        for (let row: number = 0; row < this.height; row++) {
            for (let col: number = 0; col < this.width; col++) {
                clone.pixels[row][col] = this.pixels[row][col].copy();
            }
        }
        return clone;
    }

}