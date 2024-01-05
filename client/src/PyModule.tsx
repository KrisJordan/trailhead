import { useCallback, useEffect } from "react";
import { useLoaderData, useOutletContext, useLocation } from "react-router-dom";
import { PyProcess, PyProcessState } from "./PyProcess";
import { PyProcessUI } from "./PyProcessUI";
import { useDispatch, useSelector } from "react-redux";
import { RootState } from "./app/store";
import { setProcess } from "./features/process";
import { ReadyState } from "./utils/Socket";

export function PyModule() {
    const runningProcess = useSelector<RootState, PyProcess | null>(state => state.process.active);
    const socketReadyState = useSelector<RootState, ReadyState>(state => state.socket.readyState);
    const moduleName = useLoaderData();
    const location = useLocation();
    const dispatch = useDispatch();

    const runModule = (moduleStr: string) => {
        dispatch(
            setProcess({
                path: moduleStr + ".py",
                module: moduleStr,
                state: PyProcessState.STARTING
            })
        );
        dispatch({
            type: 'socket/send',
            payload: { type: "RUN", "data": { "module": moduleStr } }
        });
    };

    let isRunning = false;

    useEffect(() => {
        if (moduleName && !isRunning && socketReadyState === ReadyState.OPEN) {
            runModule(moduleName as string);
            isRunning = true;
        }
    }, [location, socketReadyState]);

    return runningProcess !== null ? <PyProcessUI /> : <></>;
}