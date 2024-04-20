import { useDispatch, useSelector } from "react-redux";
import { RootState } from "./app/store";
import { ExprEval, StdIO } from "./StdIOTypes";
import { PyProcess, PyProcessState } from "./PyProcess";
import { ModuleInfo } from "./features/module";
import { useCallback, useEffect, useRef, useState } from "react";
import { StdOutGroupContainer } from "./StdOutGroupContainer";
import { StdErrMessage } from "./StdErrMessage";
import { Icon } from "@iconify/react/dist/iconify.js";
import { valueToInlineJSX } from "./context/helpers";

interface FunctionCall {
    type: 'function_call';
    value: string;
}

type MessageHistory = StdIO | FunctionCall;

export function GraphicalUI() {
    const pyProcess = useSelector<RootState, PyProcess | null>((state) => state.process.active);
    const moduleInfo = useSelector<RootState, ModuleInfo | null>((state) => state.module.info);
    const [guiIframe, setGuiIframe] = useState<HTMLIFrameElement | null>(null);
    const filteredStdio = useSelector<RootState, ExprEval[]>((state) => state.process.stdio.filter(line => line.type === "expr_eval") as ExprEval[]);
    const prevStdioLength = useRef<number>(filteredStdio.length);
    const dispatch = useDispatch();
    const [messageHistory, setMessageHistory] = useState<MessageHistory[]>([]);
    const [shouldShowData, setShouldShowData] = useState<boolean>(false);
    const dataView = useRef<HTMLDivElement>(null);

    // function sendTest() {
    //     dispatch({
    //         type: 'runsocket/send',
    //         payload: { type: "STDIN", "data": { "data": "my_func()", "pid": pyProcess?.pid } }
    //     });
    // }

    const handleIframe = useCallback((iframe: HTMLIFrameElement | null) => {
        setGuiIframe(iframe);
    }, []);

    const handleMessageFromChild = useCallback((event: MessageEvent<{ source: string, payload: string }>) => {
        if (event.data?.source !== "gui-template-child") return;

        setMessageHistory((oldMessages) => [...oldMessages, { type: 'function_call', value: event.data.payload }]);
        dispatch({
            type: 'runsocket/send',
            payload: { type: "STDIN", "data": { "data": event.data.payload, "pid": pyProcess?.pid } }
        });
    }, [messageHistory]);

    useEffect(() => {
        window.addEventListener('message', handleMessageFromChild);

        return () => {
            window.removeEventListener('message', handleMessageFromChild);
        }
    }, []);

    useEffect(() => {
        if (guiIframe === null || filteredStdio.length === prevStdioLength.current || filteredStdio.length <= 0) return;

        setMessageHistory((oldMessages) => [...oldMessages, filteredStdio[filteredStdio.length - 1]]);
        guiIframe.contentWindow?.postMessage({
            source: "gui-template-parent",
            payload: filteredStdio[filteredStdio.length - 1].raw_value
        }, "*");

        prevStdioLength.current = filteredStdio.length;
    }, [filteredStdio, guiIframe]);

    useEffect(() => {
        if (guiIframe === null) return;

        if (pyProcess?.state === PyProcessState.RUNNING) {
            guiIframe.src = guiIframe?.src;

            setMessageHistory([]);

            guiIframe.contentWindow?.postMessage({
                source: "gui-template-parent",
                payload: "ready"
            }, "*");
        }
    }, [pyProcess]);

    useEffect(() => {
        if (dataView.current) {
            dataView.current.scrollTop = dataView.current.scrollHeight;
        }
    }, [messageHistory]);

    return <div>
        {
            moduleInfo?.global_vars?.["__template__"] ? (
                <>
                    <iframe className="w-full h-[80vh] mb-4 border border-gray-300 rounded" src={moduleInfo?.global_vars?.["__template__"]} ref={handleIframe}></iframe>
                    <div className={`cursor-pointer collapse collapse-arrow max-h-[30vh] ${shouldShowData ? "collapse-open" : "collapse-close"}`} onClick={() => setShouldShowData(old => !old)}>
                        <div className="collapse-title">View Commands</div>
                        <div className="collapse-content overflow-scroll" ref={dataView}>
                            {messageHistory.map((line, idx) => {
                                switch (line.type) {
                                    case 'stderr':
                                        return <StdErrMessage key={idx} line={line.line} />;
                                    case 'stdout_group':
                                        return <StdOutGroupContainer key={idx} group={line} minGroupSize={100} groupAfterRatePerSecond={60} />
                                    case 'expr_eval':
                                        return <div className="display-block p-2 rounded mb-4 bg-secondary text-white font-bold text-xl">
                                            <Icon icon="mdi:lightning-bolt" className="inline icon-lg p-0.5 mr-2" width="24"></Icon>
                                            <span className="font-mono">{valueToInlineJSX(line.value, "bg-neutral rounded text-lg m-0 p-0.5")}{line.value.type !== 'unknown' ? ` (${line.value.type})` : null}</span>
                                        </div>;
                                    case 'function_call':
                                        return <div>
                                            <input value={line.value} disabled type="text" className="mb-4 input input-bordered bg-info grow  font-mono font-bold text-xl w-full" />
                                        </div>;
                                }
                            })}
                        </div>
                    </div>
                </>
            ) : (
                <div>No <code className="bg-base-300 p-1 rounded">__template__</code> variable declared.</div>
            )
        }
    </div>;
}
