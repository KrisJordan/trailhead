import { useSelector } from "react-redux";
import { ModuleState, ParameterInfo } from "./features/module";
import { RootState } from "./app/store";
import { PyProcessUI } from "./PyProcessUI";

export function ModuleREPL() {
    const module = useSelector<RootState, ModuleState>((state) => state.module);
    let functionDefinitions = module.info?.top_level_functions.map((fn, idx) =>
        <div className="collapse bg-base-200 mb-2 p-0" key={idx}>
            <input type="checkbox" />
            <div key={fn.name} className="collapse-title">
                <code className="mb-0"><span className="font-bold">{fn.name}</span>({fn.parameters.map((p: ParameterInfo, i: number) => <span key={`${i}-${p.name}`}>{i > 0 ? ', ' : ''}{p.name}: <span className="font-bold">{p.type}</span></span>)}) -&gt; <span className="font-bold">{fn.return_type}</span></code>

                <p className="italic ml-2 mt-0 mb-0 p-0 text-sm">{fn.doc}</p>
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
        <h1 className="font-bold text-xl mb-4">REPL: Read, Evaluate, Print, Loop</h1>
        <p className="mb-4 italic">The <code>{module.info?.name}</code> module definitions are loaded in the REPL below...</p>
        <PyProcessUI key={`${module.info?.name}-repl`} />
    </>
}