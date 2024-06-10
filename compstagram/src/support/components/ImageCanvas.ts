import { Image } from "../../Image";

export class ImageCanvas {

    canvas: HTMLCanvasElement;

    constructor(canvas: HTMLCanvasElement) {
        this.canvas = canvas;
        this.canvas.width = window.innerWidth - 32 < 500 ? window.innerWidth - 32 : 500;
        this.canvas.height = this.canvas.width;
    }

    update(image: Image): void {
        let ctx: CanvasRenderingContext2D = this.canvas.getContext("2d")!;
        let target: ImageData = ctx.createImageData(image.width, image.height);
        for (let i: number = 0; i < target.data.length; i += 4) {
            let row: number = Math.floor(i / 4 / target.width);
            let col: number = i / 4 % target.width;
            target.data[i] = Math.floor(image.pixels[row][col].red * 255);
            target.data[i + 1] = Math.floor(image.pixels[row][col].green * 255);
            target.data[i + 2] = Math.floor(image.pixels[row][col].blue * 255);
            target.data[i + 3] = 255;
        }
        ctx.putImageData(target, 0, 0, 0, 0, image.width, image.height);
        ctx.drawImage(this.canvas, 0, 0, this.canvas.width, this.canvas.height);
    }

}