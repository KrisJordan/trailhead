import { Message } from "../Message";

class Socket {
    socket: WebSocket | null = null

    constructor() { }

    connect() {
        if (this.socket) {
            return;
        }

        const HOST = window.location.host;
        const PROTOCOL = window.location.protocol === 'http:' ? 'ws:' : 'wss:';
        const WS_ENDPOINT = `${PROTOCOL}//${HOST}/ws`;
        this.socket = new WebSocket(WS_ENDPOINT);
    }

    isConnected() {
        return this.socket !== null;
    }

    disconnect() {
        if (this.socket) {
            this.socket.close();
            this.socket = null;
        }
    }

    send(message: Message) {
        if (this.socket) {
            this.socket.send(JSON.stringify(message));
        }
    }

    on(eventName: string, callback: any) {
        if (this.socket) {
            this.socket.addEventListener(eventName, callback);
        }
    }
}

const enum ReadyState {
    UNINITIALIZED = -1,
    CONNECTING = 0,
    OPEN = 1,
    CLOSING = 2,
    CLOSED = 3
}

export { Socket, ReadyState }