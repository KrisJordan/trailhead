export interface Observer<T> {
    (value: T): void;
}

export interface Observable<T> {
    addObserver(o: Observer<T>): void;
}