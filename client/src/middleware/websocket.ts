import { Socket } from '../utils/Socket';
import { parseJsonMessage } from '../Message';
import { update as setFiles } from '../features/files';
import { updateReadyState } from '../features/socket';
import router from "../routes";

// Explained in far more detail here: https://www.taniarascia.com/websockets-in-redux/
export const websocketMiddlewareFactory = () => {
    console.log("File socket initialized");
    let socket: Socket | null;

    return (params: any) => (next: any) => (action: any) => {
        const { dispatch } = params;
        const { type, payload } = action;

        function setReadyState(readyState: number) {
            dispatch(updateReadyState(readyState));
        }

        switch (type) {
            case 'socket/connect':
                // So we don't add duplicate event listeners
                if (socket) {
                    socket.disconnect();
                }

                socket = new Socket('/ws', 1000);

                setReadyState(0);
                socket.connect();

                socket.on('message', (data: MessageEvent) => {
                    const message = parseJsonMessage(data);
                    if (!message) {
                        return;
                    }

                    // const { process } = getState() as RootState;
                    switch (message.type) {
                        case 'LS':
                            dispatch(setFiles(message.data.files));
                            break;
                        case 'directory_modified':
                            socket?.send({ type: "LS", data: { path: "/" } });
                            break;
                        case 'file_modified':
                            router.navigate(".", { replace: true });
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
                socket?.send(payload);
                break;
            case 'socket/disconnect':
                setReadyState(2);
                socket?.disconnect();
                break;
            default:
                break;
        }

        return next(action);
    }
}