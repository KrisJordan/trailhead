import { Socket } from '../utils/Socket';
import { parseModuleFromFile } from '../utils/ModuleTools';
import { Message, parseJsonMessage } from '../Message';
import { update as setFiles } from '../features/files';
import { updateReadyState } from '../features/socket';
import { updateProcessState, appendStdIO, clearStdIO, incrementProcessRequestId } from '../features/process';
import { PyProcessState } from '../PyProcess';
import { PayloadAction, buildCreateSlice } from '@reduxjs/toolkit';
import { RootState } from '../app/store';

// Explained in far more detail here: https://www.taniarascia.com/websockets-in-redux/
export const websocketMiddlewareFactory = (socket: Socket) => (params: any) => (next: any) => (action: any) => {
    const { dispatch, getState } = params;
    const { type, payload } = action;

    function setReadyState(readyState: number) {
        dispatch(updateReadyState(readyState));
    }

    switch (type) {
        case 'socket/connect':
            // So we don't add duplicate event listeners
            if (socket.isConnected()) {
                return;
            }

            setReadyState(0);
            socket.connect();

            socket.on('message', (data: MessageEvent) => {
                const message = parseJsonMessage(data);
                if (!message) {
                    return;
                }

                const { process } = getState() as RootState;
                switch (message.type) {
                    case 'LS':
                        dispatch(setFiles(message.data.files));
                        break;
                    case 'directory_modified':
                        socket.send({ type: "LS", data: { path: "/" } });
                        break;
                    case 'RUNNING':
                        dispatch(clearStdIO());

                        if (message.data.request_id === process.active?.requestId) {
                            dispatch(
                                updateProcessState({ pid: message?.data.pid, state: PyProcessState.RUNNING })
                            );
                        }
                        break;
                    case 'STDOUT':
                        if (message.data.is_input_prompt) {
                            dispatch(
                                appendStdIO({
                                    type: 'stdin', prompt: message?.data.data
                                })
                            );
                        } else {
                            dispatch(
                                appendStdIO({
                                    type: 'stdout', line: message?.data.data
                                })
                            );
                        }
                        break;
                    case 'STDERR':
                        dispatch(
                            appendStdIO({
                                type: 'stderr', line: message?.data.data
                            })
                        );
                        break;
                    case 'INSPECT':
                        // Do something here
                        break;
                    case 'file_modified':
                        let module = parseModuleFromFile(message.data.path);
                        if (module !== process.active?.module) {
                            return;
                        }

                        if (process.active.state !== PyProcessState.EXITED && process.active.pid) {
                            socket.send({ type: "KILL", data: { pid: process.active.pid } });
                        }

                        socket.send({ type: "RUN", data: { module: process.active.module, request_id: process.active.requestId } })
                        clearStdIO();
                        break;
                    case 'EXIT':
                        if (message.data.pid === process.active?.pid) {
                            dispatch(
                                updateProcessState({ state: PyProcessState.EXITED })
                            );
                        }
                        // socket.send({ type: "INSPECT", data: { path: process.active.path } })
                        break;
                }
            });

            socket.on('open', () => {
                setReadyState(1);
            });

            socket.on('close', () => {
                setReadyState(3);
            });

            socket.on('error', () => {
                setReadyState(3);
            });
            break;
        case 'socket/send':
            if (payload.type === "RUN") {
                dispatch(incrementProcessRequestId());

                let { process } = getState() as RootState;
                if (process.active) {
                    payload.data.request_id = process.active.requestId;
                }
            }

            socket.send(payload);
            break;
        case 'socket/disconnect':
            setReadyState(2);
            socket.disconnect();
            break;
        default:
            break;
    }

    return next(action);
}