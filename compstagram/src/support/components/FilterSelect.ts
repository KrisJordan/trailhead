import { Filter } from "../../Filter";
import { Observer, Observable } from "./Observers";

export class FilterSelect implements Observable<Filter> {

    filters: Filter[];
    names: string[];
    select: HTMLSelectElement;
    button: HTMLButtonElement;
    observers: Observer<Filter>[] = [];

    constructor(filters: Filter[], select: HTMLSelectElement, button: HTMLButtonElement) {
        this.filters = filters;
        this.names = filters.map((f: Filter): string => f.name);
        this.select = select;
        this.button = button;

        this.initOptions();
        this.initEvents();
    }

    addObserver(o: Observer<Filter>): void {
        this.observers.push(o);
    }

    private click(event: MouseEvent): void {
        if (this.select.value === "") {
            // Nothing is selected.
            return;
        }

        // Clone the filter settings...
        let filterSettings: Filter = this.filters[parseInt(this.select.value, 10)];
        let filter: Filter = new Filter();
        filter.name = filterSettings.name;
        filter.amount = filterSettings.amount;
        this.observers.forEach((o: Observer<Filter>) => {
            o(filter);
        });
    }

    private initEvents(): void {
        this.button.onclick = this.click.bind(this);
    }

    private initOptions(): void {
        this.names
            .map((name: string, index: number): HTMLOptionElement => {
                let option: HTMLOptionElement = document.createElement("option");
                option.innerText = name;
                option.value = String(index);
                return option;
            })
            .forEach((option: HTMLOptionElement) => this.select.appendChild(option));
    }

}