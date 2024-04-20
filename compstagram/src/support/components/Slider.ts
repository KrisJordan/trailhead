import { Observable, Observer } from "./Observers";

export class Slider implements Observable<number> {

    parent: Element;
    handle: SVGCircleElement;

    private isDragging: boolean = false;
    private _value: number = 0.0;
    private _observers: Observer<number>[] = [];

    constructor(parent: Element) {
        this.parent = parent;
        this.initShapes();
        this.initEventHandlers();
    }

    addObserver(o: Observer<number>): void {
        this._observers.push(o);
    }

    private initShapes(): void {
        let guide: SVGRectElement = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        guide.setAttribute("class", "guide");
        guide.setAttribute("x", "10");
        guide.setAttribute("y", "14");
        guide.setAttribute("stroke-linecap", "round");
        guide.setAttribute("stroke-linejoin", "round");
        this.parent.appendChild(guide);

        let handle: SVGCircleElement = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        handle.setAttribute("class", "handle");
        handle.setAttribute("r", "10");
        handle.setAttribute("cy", "15");
        handle.setAttribute("cx", "10");
        this.parent.appendChild(handle);
        this.handle = handle;
    }

    private initEventHandlers(): void {
        this.handle.parentElement!.onmousedown = this.mousedown.bind(this);
        this.handle.parentElement!.onmousemove = this.mousemove.bind(this);
        this.handle.parentElement!.onmouseup = this.mouseup.bind(this);
        this.handle.parentElement!.onmouseleave = this.mouseup.bind(this);
        this.handle.parentElement!.onclick = this.click.bind(this);
    }

    private mousedown(event: MouseEvent): void {
        this.isDragging = true;
        this.mousemove(event);
    }

    private mousemove(event: MouseEvent): void {
        if (this.isDragging) {
            this.updateValue(event);
            event.preventDefault();
        }
    }

    private updateValue(event: MouseEvent): void {
        let radius: number = parseInt(this.handle.getAttribute("r")!, 10);
        let width: number = this.parent.clientWidth - 2 * radius;
        let offset: number = (event.offsetX - radius) / width;
        if (offset < 0) {
            offset = 0;
        } else if (offset > 1.0) {
            offset = 1;
        }
        this.value = offset;
    }

    private click(event: MouseEvent): void {
        this.updateValue(event);
    }

    private mouseup(): void {
        this.isDragging = false;
    }

    set value(value: number) {
        this._value = value;
        let radius: number = parseInt(this.handle.getAttribute("r")!, 10);
        let width: number = this.parent.clientWidth - 2 * radius;
        let cx: number = radius + width * this._value;
        this.handle.setAttribute("cx", "" + cx);
        this.emit();
    }

    get value(): number {
        return this._value;
    }

    private emit(): void {
        this._observers.forEach((o: Observer<number>) => o(this._value));
    }

}