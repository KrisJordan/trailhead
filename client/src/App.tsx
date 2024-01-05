import { useEffect, useState } from 'react'
import NamespaceTree from './NamespaceTree';
// import { Module } from './NamespaceTree';
import { PyProcess } from './PyProcess';
import { Outlet } from 'react-router-dom';
import { Icon } from '@iconify/react';

import './App.css';
import { useDispatch, useSelector } from 'react-redux';
// import { parseModuleFromFile } from './utils/ModuleTools';
// import { clearStdIO } from './features/process';
import { RootState } from './app/store';

function App() {
    // const [messageHistory, setMessageHistory] = useState<string[]>([]);
    // const [runningProcess, setRunningProcess] = useState<PyProcess | null>(null);
    const runningProcess = useSelector<RootState, PyProcess | null>(state => state.process.active);
    // const [requestId, setRequestId] = useState<number>(0);
    const [showFiles, setShowFiles] = useState<boolean>(true);
    const dispatch = useDispatch();
    // const navigate = useNavigate();

    useEffect(() => {
        dispatch({ type: 'socket/connect' });

        return () => {
            dispatch({ type: 'socket/disconnect' });
        }
    }, []);

    // useEffect(() => {
    //     if (lastJsonMessage && Object.keys(lastJsonMessage).length !== 0) {
    //         let message = lastJsonMessage as Message;
    //         setMessageHistory(prev => prev.concat(message.type));
    //     }
    // }, [lastJsonMessage, setMessageHistory]);

    // const connectionStatus = {
    //     [ReadyState.CONNECTING]: 'Connecting',
    //     [ReadyState.OPEN]: 'Open',
    //     [ReadyState.CLOSING]: 'Closing',
    //     [ReadyState.CLOSED]: 'Closed',
    //     [ReadyState.UNINSTANTIATED]: 'Uninstantiated',
    // }[readyState];

    // function routeToModuleRunner(module: Module) {
    //     let moduleStr = parseModuleFromFile(module.full_path);
    //     dispatch(clearStdIO());
    //     navigate(`/module/${moduleStr}/run`);
    // }

    return <>
        <div className="navbar bg-neutral text-neutral-content rounded-box">
            <button onClick={() => { setShowFiles(prev => !prev) }}>
                <Icon className="mx-3" icon={showFiles ? "ph:x" : "ci:hamburger-md"} height={25} />
            </button>
            <div className="text-xl flex-1 ml-2 text-white font-black">{runningProcess ? runningProcess.module : 'Select a Module'}</div>
        </div>
        <div className="flex">
            <div className={`flex-none ${!showFiles && 'hidden'}`}>
                <NamespaceTree />
            </div>
            <div className="mt-4 container">
                <Outlet />
            </div>
        </div>
        {/* <ul className="hidden">
            {messageHistory.map((message, idx) => (
                <li key={idx}>{message}</li>
            ))}
        </ul> */}
    </>;
}

export default App;
