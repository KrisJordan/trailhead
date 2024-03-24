import { useDispatch, useSelector } from "react-redux";
import { RootState } from "./app/store";
import { ExprEval, StdIO } from "./StdIOTypes";
import { PyProcess } from "./PyProcess";
import { ModuleInfo } from "./features/module";

export function GraphicalUI() {
    const pyProcess = useSelector<RootState, PyProcess | null>((state) => state.process.active);
    const moduleInfo = useSelector<RootState, ModuleInfo | null>((state) => state.module.info);
    const stdio = useSelector<RootState, ExprEval[]>((state) => state.process.stdio.filter(line => line.type === "expr_eval") as ExprEval[]);
    const dispatch = useDispatch();

    function sendTest() {
        dispatch({
            type: 'runsocket/send',
            payload: { type: "STDIN", "data": { "data": "my_func()", "pid": pyProcess?.pid } }
        });
    }
    return <div>
        {/* {stdio.map((line, idx) => {
            return <div key={idx}>{JSON.stringify(line.value)}</div>
        })} */}
        {/* This is where the UI goes
        <br></br>
        {stdio.length > 0 && JSON.stringify(stdio[stdio.length - 1].value)}
        <div className="btn btn-primary ml-4" onClick={sendTest}>Click Me</div> */}
        {
            moduleInfo?.global_vars?.["__template__"] ? (
                <iframe className="w-full h-[70vh]" src={moduleInfo?.global_vars?.["__template__"]}></iframe>
            ) : (
                <div>No <code className="bg-base-300 p-1 rounded">__template__</code> variable declared.</div>
            )
        }
    </div>;
}