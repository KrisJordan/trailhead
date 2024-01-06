// import { useOutletContext } from "react-router-dom";
import { useSelector } from "react-redux";
import { PyProcessUI } from "./PyProcessUI";
import { RootState } from "./app/store";
import { ModuleState } from "./features/module";

export function ModuleRunner() {
    const module = useSelector<RootState, ModuleState>((state) => state.module);
    return <div>
        <PyProcessUI key={`${module.info?.name}-repl`} />
    </div>;
}