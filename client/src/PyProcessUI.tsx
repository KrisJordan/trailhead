import React, { useCallback, useState } from "react";
import { PyProcess, PyProcessState } from "./PyProcess";
import { StdErrMessage } from "./StdErrMessage";
import { StdOutGroupContainer } from "./StdOutGroupContainer";
import { StdIO } from "./StdIOTypes";
import { useDispatch, useSelector } from "react-redux";
import { RootState } from "./app/store";
import { updateStdIn } from "./features/process";


export function PyProcessUI() {
    const pyProcess = useSelector<RootState, PyProcess | null>((state) => state.process.active);
    const stdio = useSelector<RootState, StdIO[]>((state) => state.process.stdio);
    const [stdinValue, setStdinValue] = useState<string>("");
    const dispatch = useDispatch();

    // const runAgain = () => {
    //     dispatch({
    //         type: 'socket/send',
    //         payload: { type: "RUN", data: { module: pyProcess?.module } }
    //     })
    //     dispatch(clearStdIO());
    // };

    let status: string = "";
    let statusBadgeClass: string = "mb-4 badge ";
    console.log('pyProcess', pyProcess);
    switch (pyProcess?.state) {
        case PyProcessState.STARTING:
            status = 'Starting...';
            statusBadgeClass += 'badge-secondary';
            break;
        case PyProcessState.RUNNING:
            status = 'Running';
            statusBadgeClass += 'badge-primary';
            break;
        case PyProcessState.EXITED:
            status = 'Exited';
            statusBadgeClass += 'badge-neutral badge-outline';
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

    return <div>
        <div className={statusBadgeClass}>{status}</div>
        {/* {runAgainButton} */}
        {stdio.map((line, idx) => {
            switch (line.type) {
                case 'stdin':
                    if (line.response === undefined) {
                        return <div key={idx} className="mb-4 text-xl">
                            <div className="mb-4">{line.prompt}</div>
                            <div className="flex">
                                <input onChange={handleStdInChange} onKeyUp={(e) => { if (e.key === 'Enter') { handleStdInSend(idx); } }} value={stdinValue} autoFocus={true} type="text" className="input input-bordered bg-info grow"></input>
                                <button onClick={() => handleStdInSend(idx)} className="btn btn-primary ml-4">Send</button>
                            </div>
                        </div>
                    } else {
                        return <p key={idx} className="mb-4 text-xl">{line.prompt}<br />
                            <input autoFocus={true} type="text" className="input input-bordered w-full max-w-xs" value={line.response} disabled={true}></input>
                        </p>
                    }
                case 'stderr':
                    return <StdErrMessage key={idx} line={line.line} />;
                case 'stdout_group':
                    return <StdOutGroupContainer key={idx} group={line} minGroupSize={100} groupAfterRatePerSecond={60} />
            }
        })}
    </div>;
}