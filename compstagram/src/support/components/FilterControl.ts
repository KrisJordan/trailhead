import { Slider } from "./Slider";
import { Filter } from "../../Filter";
import { Observer, Observable } from "./Observers";

export class FilterControl implements Observable<number> {

    parent: HTMLElement;
    filter: Filter;
    slider: Slider;
    amount: HTMLSpanElement;
    removeButton: HTMLButtonElement;
    observers: Observer<number>[] = [];
    onremove: Observer<Filter> | null = null;
    element: HTMLElement;

    constructor(parent: HTMLElement, filter: Filter) {
        this.parent = parent;
        this.filter = filter;
        this.element = this.initElement();
    }

    addObserver(o: Observer<number>): void {
        this.observers.push(o);
    }

    private initElement(): HTMLElement {
        let div: HTMLDivElement = document.createElement("div");
        div.setAttribute("class", "filter");

        let text: HTMLHeadingElement = document.createElement("h2");
        text.setAttribute("class", "title");
        text.innerText = this.filter.name;
        div.appendChild(text);

        this.amount = document.createElement("span");
        this.amount.setAttribute("class", "amount");
        this.updateAmountSpan();
        text.appendChild(this.amount);

        let svg: SVGElement = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        svg.setAttribute("class", "slider");
        this.slider = new Slider(svg);
        div.appendChild(svg);

        this.removeButton = document.createElement("button");
        this.removeButton.setAttribute("class", "btn btn-sm btn-dark");
        this.removeButton.innerText = "X";
        this.removeButton.onclick = this.remove.bind(this);
        div.appendChild(this.removeButton);

        // Finally, append to parent element and initialize slider value
        this.parent.appendChild(div);
        this.slider.value = this.filter.amount;
        this.slider.addObserver(this.changeAmount.bind(this));

        return div;
    }

    private changeAmount(amount: number): void {
        this.filter.amount = amount;
        this.updateAmountSpan();
        this.observers.forEach((o: Observer<number>) => o(amount));
    }

    private updateAmountSpan(): void {
        this.amount.innerHTML = " " + Math.round(this.filter.amount * 100) + "%";
    }

    private remove(): void {
        if (this.onremove !== null) {
            this.onremove(this.filter);
        }
    }

}