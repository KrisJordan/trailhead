import { Image } from "../Image";
import { Filter } from "../Filter";
import { FilterClass } from "./FilterClass";

export class Model {

    image: Image;
    filterClasses: FilterClass[] = [];
    filters: Filter[] = [];

    process(input: Image): Image {
        return this.filters.reduce(
            function(memo: Image, filter: Filter): Image {
                return filter.process(memo);
            }, 
            input
        );
    }

}