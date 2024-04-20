import { Filter } from "../../Filter";
import { Observer, Observable } from "./Observers";

type FilterClass = typeof Filter;

export class FilterSelect implements Observable<Filter> {

    filters: FilterClass[];
    names: string[];
    select: HTMLSelectElement;
    button: HTMLButtonElement;
    observers: Observer<Filter>[] = [];

    constructor(filters: FilterClass[], select: HTMLSelectElement, button: HTMLButtonElement) {
        this.filters = filters;
        this.names = filters.map( (f: FilterClass): string => (new f()).name );
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
        
        let filter: Filter = new this.filters[parseInt(this.select.value, 10)]();
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