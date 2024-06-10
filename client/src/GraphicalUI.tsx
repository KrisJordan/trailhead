import { useDispatch, useSelector } from "react-redux";
import { RootState } from "./app/store";
import { ExprEval, StdIO } from "./StdIOTypes";
import { PyProcess, PyProcessState } from "./PyProcess";
import { ModuleInfo } from "./features/module";
import { useCallback, useEffect, useRef, useState } from "react";
import { StdOutGroupContainer } from "./StdOutGroupContainer";
import { StdErrMessage } from "./StdErrMessage";

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
    const stdio = useSelector<RootState, StdIO[]>((state) => state.process.stdio);
    const prevStdioLength = useRef<number>(filteredStdio.length);
    const dispatch = useDispatch();
    const [messageHistory, setMessageHistory] = useState<MessageHistory[]>([]);
    const [shouldShowData, setShouldShowData] = useState<boolean>(false);
    const dataView = useRef<HTMLDivElement>(null);

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
            let ready = () => {
                guiIframe.contentWindow?.postMessage({
                    source: "gui-template-parent",
                    payload: "ready"
                }, "*");
                guiIframe.removeEventListener("load", ready);
            };
            guiIframe.addEventListener("load", ready);
            guiIframe.src = guiIframe?.src.replace(/\?.*/, "") + "?v=" + Math.random();
            setMessageHistory([]);
            prevStdioLength.current = 0;
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
                        <div className="collapse-title">View Printed Output</div>
                        <div className="collapse-content overflow-scroll" ref={dataView}>
                            {stdio.map((line, idx) => {
                                switch (line.type) {
                                    case 'stderr':
                                        return <StdErrMessage key={idx} line={line.line} />;
                                    case 'stdout_group':
                                        return <StdOutGroupContainer key={idx} group={line} minGroupSize={100} groupAfterRatePerSecond={60} />
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
