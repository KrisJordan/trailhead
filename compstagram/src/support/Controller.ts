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
        this.loadFilters();
        this.loader = new ImageLoader(this.view.imageSelect, this.view.imgWidth(), this.view.imgWidth());
        this.loader.onload = this.loadImage.bind(this);
        this.loader.img.src = this.view.defaultImage;
        this.view.onfilterchange = this.update.bind(this);
        this.view.onremovefilter = this.removeFilter.bind(this);
        this.view.save.addEventListener("click", this.save.bind(this));
    }

    private loadFilters(): void {
        type FilterSettings = { name: string, amount: number };
        executeCode<FilterSettings[]>(`get_filter_types()`).then(value => {
            let availableFilters = value.map((settings) => {
                let filter = new Filter();
                filter.name = settings.name;
                filter.amount = settings.amount;
                return filter;
            });
            this.model.availableFilters = availableFilters;
            this.view.updateFiltersSelect();
            this.view.filterSelect.addObserver(this.addFilter.bind(this));
        });
    }

    private loadImage(image64: string): void {
        console.log(image64);
        this.model.image64 = image64;
        this.process();
    }

    private process() {
        console.log("PROCESSING");
        type Filter = { name: string, amount: number };
        let payload = {
            "filters": this.model.filters,
            "image": this.model.image64
        };
        executeCode<string>(`main('${JSON.stringify(payload)}')`).then((data) => {
            console.log("Processing data...");
            console.log(data);
            let image = document.createElement("img");
            // image.width = this.loader.img.width;
            // image.height = this.loader.img.height;
            image.onload = () => {
                let ctx = this.view.imageCanvas.canvas.getContext("2d");
                ctx.clearRect(0, 0, image.width, image.height);
                ctx.drawImage(image, 0, 0);
            };
            image.src = data;
            console.log("<<< Filter response...");
            console.log(payload.filters);
        });
        console.log(">>> Filter request...");
        console.log(payload.filters);
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
        if (this.model.image64 !== undefined) {
            this.process();
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