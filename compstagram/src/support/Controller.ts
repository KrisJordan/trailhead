import { Model } from "./Model";
import { View } from "./View";
import { Filter } from "../Filter";
import { ImageLoader } from "./ImageLoader";
import { Image } from "../Image";
import { executeCode } from "./bridge";

export class Controller {

    model: Model;
    view: View;

    loader: ImageLoader;

    constructor(model: Model, view: View) {
        this.model = model;
        this.view = view;
        this.initEventHandlers();
    }

    private initEventHandlers(): void {
        this.loader = new ImageLoader(this.view.imageSelect, this.view.imgWidth(), this.view.imgWidth());
        this.loader.onload = this.loadImage.bind(this);
        this.loader.img.src = this.view.defaultImage;
        this.view.filterSelect.addObserver(this.addFilter.bind(this));
        this.view.onfilterchange = this.update.bind(this);
        this.view.onremovefilter = this.removeFilter.bind(this);
        this.view.save.addEventListener("click", this.save.bind(this));
    }

    private loadImage(image: Image): void {
        this.model.image = image;
        this.update();
        let base64 = this.view.imageCanvas.canvas.toDataURL("image/png");
        executeCode<string>(`loadImage("${base64}")`).then((data) => {
            let image = new window.Image();
            image.onload = () => {
                let ctx = this.view.imageCanvas.canvas.getContext("2d");
                ctx.clearRect(0, 0, image.width, image.height);
                ctx.drawImage(image, 0, 0);
            };
            image.src = data;
        });
    }

    private addFilter(filter: Filter): void {
        this.model.filters.push(filter);
        this.view.updateFilters();
        this.update();
    }

    private removeFilter(filter: Filter): void {
        let index: number = this.model.filters.indexOf(filter);
        this.model.filters.splice(index, 1);
        this.view.updateFilters();
        this.update();
    }

    private update(): void {
        if (this.model.image !== undefined) {
            this.view.imageCanvas.update(this.model.process(this.model.image));
        }
    }

    private save(event: MouseEvent): void {
        let filename: string | null = prompt("What filename?", "compstagram");
        if (filename !== null) {
            this.view.save.href = this.view.viewport.toDataURL();
            this.view.save.download = filename + ".png";
        } else {
            event.preventDefault();
        }
    }

}