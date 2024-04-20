import { View } from "./support/View";
import { Model } from "./support/Model";
import { Controller } from "./support/Controller";

import {
    InvertFilter,
    BorderFilter,
    BrightnessFilter,
    ColorizeFilter,
    ContrastFilter,
    SaturationFilter
} from "./compstagram-filters";

let main = async () => {

    let model = new Model();

    // TODO: As you work begin work on each filter, comment it out.
    model.filterClasses = [
        // SaturationFilter,
        // ContrastFilter,
        // ColorizeFilter,
        // BrightnessFilter,
        // BorderFilter,
        InvertFilter
    ];

    let view = new View(model);
    let controller = new Controller(model, view);

};

window.addEventListener('load', main);