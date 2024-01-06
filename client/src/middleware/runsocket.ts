import { Socket } from '../utils/Socket';
// import { updateReadyState } from '../features/socket';

import { updateProcessState, appendStdIO, clearStdIO, setProcess } from '../features/process';
import { PyProcessState } from '../PyProcess';
import { RootState } from '../app/store';
import { parseJsonMessage } from '../Message';

export const runsocketMiddlewareFactory = () => {

    console.log("Run socket initialized");
    let socket: Socket | null;

    return (params: any) => {
        const { dispatch, getState } = params;
        // function setReadyState(readyState: number) {
        //     // dispatch(updateReadyState(readyState));
        // }

        return (next: any) => (action: any) => {
            const { type, payload } = action as { type: string, payload: any };
            if (!type.startsWith("runsocket")) {
                return next(action);
            }

            switch (type) {
                case 'runsocket/connect':
                    if (socket) {
                        socket.disconnect();
                    }
                    const endpoint = payload.endpoint as string;
                    socket = new Socket(endpoint);

                    // setReadyState(0);
                    socket.connect();

                    socket.on('open', () => {
                        // setReadyState(WebSocket.OPEN);
                    });

                    socket.on('message', (data: MessageEvent) => {
                        const message = parseJsonMessage(data);

                        if (!message) {
                            return;
                        }

                        let { process } = getState() as RootState;

                        // const { process } = getState() as RootState;
                        switch (message.type) {
                            case 'RUNNING':
                                dispatch(clearStdIO());
                                dispatch(setProcess({ pid: message?.data.pid, module: 'foo', path: 'foo', state: PyProcessState.RUNNING }));
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
                            case 'EXIT':
                                console.log('done');
                                if (message.data.pid === process.active?.pid) {
                                    dispatch(
                                        updateProcessState({ state: PyProcessState.EXITED })
                                    );
                                }
                                break;
                        }
                    });

                    socket.on('error', () => {
                        // setReadyState(WebSocket.CLOSED);
                    });

                    socket.on('closed', () => {
                        // setReadyState(WebSocket.CLOSED);
                    });
                    break;

                case 'runsocket/send':
                    socket?.send(payload);
                    break;

                case 'runsocket/disconnect':
                    // setReadyState(2);
                    socket?.disconnect();
                    break;

                default:
                    break;
            }

            return next(action);
        };
    }
}