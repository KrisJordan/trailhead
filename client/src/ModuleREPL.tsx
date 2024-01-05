import { useSelector } from "react-redux";
import { ModuleState, ParameterInfo } from "./features/module";
import { RootState } from "./app/store";

export function ModuleREPL() {
    const module = useSelector<RootState, ModuleState>((state) => state.module);
    let functionDefinitions = module.info?.top_level_functions.map((fn, idx) =>
        <div className="collapse bg-base-200 mb-2 p-0" key={idx}>
            <input type="checkbox" />
            <div key={fn.name} className="collapse-title">
                <code className="mb-0">{fn.name}({fn.parameters.map((p: ParameterInfo) => `${p.name}: ${p.type}`).join(", ")}) -&gt; {fn.return_type}</code>
                <p className="italic ml-2 mt-0 mb-0 p-0">{fn.doc}</p>
            </div>
            <div className="collapse-content">
                <pre className="bg-primary p-4 rounded-lg"><code>{fn.source}</code></pre>
            </div>
        </div>
    );
    return <>
        <h1 className="font-bold text-xl mb-4">Functions Defined</h1>
        {functionDefinitions}
        <div className="divider lg:divider-vertical divider-secondary" />
        <h1 className="font-bold text-xl mb-4">Interactive REPL...</h1>
        <h2>TODO</h2>
    </>
}