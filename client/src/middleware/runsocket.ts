import { Socket } from '../utils/Socket';
import { updateReadyState } from '../features/socket';

export const runsocketMiddlewareFactory = () => {

    console.log("Run socket initialized");
    let socket: Socket | null;

    return (params: any) => {
        const { dispatch } = params;
        function setReadyState(readyState: number) {
            dispatch(updateReadyState(readyState));
        }

        return (next: any) => (action: any) => {

            const { type, payload } = action as { type: string, payload: any };
            if (!type.startsWith("runsocket")) {
                console.log(type);
                return next(action);
            }

            switch (type) {
                case 'runsocket/connect':
                    if (socket) {
                        socket.disconnect();
                    }
                    const endpoint = payload.endpoint as string;
                    socket = new Socket(endpoint);

                    setReadyState(0);

                    socket.on('open', () => {
                        setReadyState(WebSocket.OPEN);
                    });

                    socket.on('closed', () => {
                        setReadyState(WebSocket.CLOSED);
                    });

                    socket.on('error', () => {
                        setReadyState(WebSocket.CLOSED);
                    });

                    socket.connect();
                    break;
                case 'runsocket/disconnect':
                    setReadyState(2);
                    socket?.disconnect();
                    break;
                default:
                    break;
            }

            return next(action);
        };
    }
}