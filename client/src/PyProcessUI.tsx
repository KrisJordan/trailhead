import React, { useCallback, useState } from "react";
import { PyProcess, PyProcessState } from "./PyProcess";
import { StdErrMessage } from "./StdErrMessage";
import { StdOutGroupContainer } from "./StdOutGroupContainer";
import { StdIO } from "./StdIOTypes";
import { useDispatch, useSelector } from "react-redux";
import { RootState } from "./app/store";
import { updateStdIn } from "./features/process";
import { NavLink } from "react-router-dom";
import { Icon } from "@iconify/react/dist/iconify.js";
import { ReadyState } from "./utils/Socket";
import { valueToInlineJSX } from "./context/helpers";


export function PyProcessUI() {
    const pyProcess = useSelector<RootState, PyProcess | null>((state) => state.process.active);
    const stdio = useSelector<RootState, StdIO[]>((state) => state.process.stdio);
    const runReadyState = useSelector<RootState, ReadyState>((state) => state.socket.runSocketReadyState);
    const [stdinValue, setStdinValue] = useState<string>("");
    const dispatch = useDispatch();

    let status: string = "";
    let statusBadgeClass: string = "mb-4 badge ";
    let footer: JSX.Element | null = null;

    switch (pyProcess?.state) {
        case PyProcessState.STARTING:
            status = 'Starting';
            statusBadgeClass += 'badge-neutral badge-outline';
            footer = <div className="text-right mt-8">
                <div className={statusBadgeClass}>{status}</div>
            </div>;
            break;
        case PyProcessState.RUNNING:
            status = 'Running';
            statusBadgeClass += 'badge-neutral';
            footer = <div className="text-right mt-8">
                <div className="tooltip tooltip-neutral" data-tip={`Running Process ID: ${pyProcess.pid}`}>
                    <div className={statusBadgeClass}>{status}</div>
                </div>
            </div>;
            break;
        case PyProcessState.EXITED:
            status = 'Exited';
            statusBadgeClass += 'badge-neutral badge-outline mr-4';
            if (stdio.length === 0) {
                footer = <div className="text-xl">
                    <p className="mb-4"><span className={statusBadgeClass}>{status}</span> Running <strong><code>{pyProcess.module}</code></strong> as a module exited without output. If this is unexpected, try:</p>
                    <ul className="list-decimal">
                        <li className="ml-8 mb-4">Saving your work in the <strong><code>{pyProcess.module}</code></strong> module.</li>
                        <li className="ml-8 mb-4"><NavLink to={`/module/${pyProcess.module}/repl`} className="btn btn-secondary text-white ml-2">Interacting with <code>{pyProcess.module}</code> in the REPL</NavLink></li>
                        <li className="ml-8 mb-4"><NavLink to={`/module/${pyProcess.module}/run`} className="btn btn-primary ml-2">Rerunning <code>{pyProcess.module}</code></NavLink></li>
                    </ul>
                </div>
            } else {
                footer = <div className="text-right">
                    <div className="divider mb-4"></div>
                    <div className={statusBadgeClass}>{status}</div> <NavLink to={`/module/${pyProcess.module}/run`} className="btn btn-primary ml-2"><Icon icon="mdi:reload"></Icon> Run Again</NavLink>
                </div>;
            }
            break;
    }

    const handleStdInChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        setStdinValue(event.target.value);
    };

    const handleStdInSend = useCallback((lineIndex: number) => {
        setStdinValue("");
        dispatch(
            updateStdIn({
                lineIndex: lineIndex,
                stdinValue: stdinValue
            })
        );
        dispatch({
            type: 'runsocket/send',
            payload: { type: "STDIN", "data": { "data": stdinValue, "pid": pyProcess?.pid } }
        });
    }, [stdinValue, pyProcess]);

    const isDisabled = runReadyState !== ReadyState.OPEN && pyProcess?.state !== PyProcessState.EXITED;

    return <div>
        {/* {runAgainButton} */}
        <div className={`${isDisabled && 'disabled'}`}>
            {stdio.map((line, idx) => {
                switch (line.type) {
                    case 'stdin':
                        let linePrompt;
                        if (line.prompt !== ">>> ") {
                            linePrompt = <div className="mb-4">{line.prompt}</div>;
                        } else {
                            linePrompt = null;
                        }

                        if (line.response === undefined) {
                            return <div key={idx} className="mb-4 text-xl">
                                {linePrompt}
                                <div className="flex">
                                    <input onChange={handleStdInChange} onKeyUp={(e) => { if (e.key === 'Enter') { handleStdInSend(idx); } }} value={stdinValue} autoFocus={true} type="text" className="input input-bordered bg-info grow"></input>
                                    <button onClick={() => handleStdInSend(idx)} className="btn btn-primary ml-4">Send</button>
                                </div>
                            </div>
                        } else {
                            return <div key={idx} className="mb-4 text-xl">
                                {linePrompt}
                                <div className="flex">
                                    <input autoFocus={true} type="text" className="input input-bordered flex-1" value={line.response} disabled={true}></input>
                                </div>
                            </div>
                        }
                    case 'stderr':
                        return <StdErrMessage key={idx} line={line.line} />;
                    case 'stdout_group':
                        return <StdOutGroupContainer key={idx} group={line} minGroupSize={100} groupAfterRatePerSecond={60} />
                    case 'expr_eval':
                        return <div className="display-block p-2 rounded mb-4 bg-secondary text-white font-bold">
                            <Icon icon="mdi:lightning-bolt" className="inline icon-lg p-0.5 mr-2" width="24"></Icon>
                            <span className="font-mono">{valueToInlineJSX(line.value, "bg-neutral rounded text-lg m-0 p-0.5")}{line.value.type !== 'unknown' ? ` (${line.value.type})` : null}</span>
                        </div>;
                }
            })}
        </div>
        {footer}
    </div>;
}