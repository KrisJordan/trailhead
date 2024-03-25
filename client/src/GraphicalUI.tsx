import { useDispatch, useSelector } from "react-redux";
import { RootState } from "./app/store";
import { ExprEval, StdIO } from "./StdIOTypes";
import { PyProcess } from "./PyProcess";
import { ModuleInfo } from "./features/module";
import { useCallback, useEffect, useRef, useState } from "react";

export function GraphicalUI() {
    const pyProcess = useSelector<RootState, PyProcess | null>((state) => state.process.active);
    const moduleInfo = useSelector<RootState, ModuleInfo | null>((state) => state.module.info);
    const [guiIframe, setGuiIframe] = useState<HTMLIFrameElement | null>(null);
    const stdio = useSelector<RootState, ExprEval[]>((state) => state.process.stdio.filter(line => line.type === "expr_eval") as ExprEval[]);
    const prevStdioLength = useRef<number>(stdio.length);
    const dispatch = useDispatch();

    // function sendTest() {
    //     dispatch({
    //         type: 'runsocket/send',
    //         payload: { type: "STDIN", "data": { "data": "my_func()", "pid": pyProcess?.pid } }
    //     });
    // }

    const handleIframe = useCallback((iframe: HTMLIFrameElement | null) => {
        setGuiIframe(iframe);
    }, []);

    function handleMessageFromChild(event: MessageEvent<{ source: string, payload: string }>) {
        if (event.data?.source !== "gui-template-child") return;

        dispatch({
            type: 'runsocket/send',
            payload: { type: "STDIN", "data": { "data": event.data.payload, "pid": pyProcess?.pid } }
        });
    }

    useEffect(() => {
        window.addEventListener('message', handleMessageFromChild);

        return () => {
            window.removeEventListener('message', handleMessageFromChild);
        }
    }, []);

    useEffect(() => {
        if (guiIframe === null || stdio.length === prevStdioLength.current || stdio.length <= 0) return;

        guiIframe.contentWindow?.postMessage({
            source: "gui-template-parent",
            payload: stdio[stdio.length - 1].value
        }, "*");

        prevStdioLength.current = stdio.length;
    }, [stdio, guiIframe]);

    useEffect(() => {
        if (guiIframe === null) return;

        guiIframe.src = guiIframe?.src;
    }, [pyProcess]);

    return <div>
        {/* {stdio.map((line, idx) => {
            return <div key={idx}>{JSON.stringify(line.value)}</div>
        })} */}
        {/* This is where the UI goes
        <br></br>
        {stdio.length > 0 && JSON.stringify(stdio[stdio.length - 1].value)}
        <div className="btn btn-primary ml-4" onClick={sendTest}>Click Me</div> */}
        {pyProcess?.state}
        <br></br>
        {/* {JSON.stringify(stdio)} */}
        {
            moduleInfo?.global_vars?.["__template__"] ? (
                <iframe className="w-full h-[70vh] border-2 border-black" src={moduleInfo?.global_vars?.["__template__"]} ref={handleIframe}></iframe>
            ) : (
                <div>No <code className="bg-base-300 p-1 rounded">__template__</code> variable declared.</div>
            )
        }
    </div>;
}
