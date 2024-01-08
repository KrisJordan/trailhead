import { useSelector } from "react-redux";
import { ModuleState } from "./features/module";
import { RootState } from "./app/store";
import { PyProcessUI } from "./PyProcessUI";
import { ContextUI } from "./context/ContextUI";

export function ModuleREPL() {
    const module = useSelector<RootState, ModuleState>((state) => state.module);
    return <>
        <h1 className="font-bold text-xl mb-4">Globals</h1>
        <ContextUI context={module.context} />
        <div className="divider lg:divider-vertical divider-secondary" />
        <h1 className="font-bold text-xl mb-4">REPL: Read, Evaluate, Print, Loop</h1>
        <p className="mb-4 italic">The <code>{module.info?.name}</code> module definitions are loaded in the REPL below...</p>
        <PyProcessUI key={`${module.info?.name}-repl`} />
    </>
}