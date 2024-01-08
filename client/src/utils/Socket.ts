import { Message } from "../Message";

interface EventHandlerCollection {
    [evt: string]: ((data?: any) => {})[]
}

const WebSocketEvents = ["close", "error", "message", "open"];

class Socket {
    socket: WebSocket | null = null
    eventHandlers: EventHandlerCollection = {};

    // Any negative value for reconnectTimeout indicates it should not try to reconnect
    constructor(
        private path: string = "/ws",
        private reconnectTimeout: number = -1
    ) { }

    connect() {
        if (this.socket) {
            return;
        }

        const HOST = window.location.host;
        const PROTOCOL = window.location.protocol === 'http:' ? 'ws:' : 'wss:';
        const WS_ENDPOINT = `${PROTOCOL}//${HOST}${this.path}`;
        this.socket = new WebSocket(WS_ENDPOINT);

        for (let eventName of WebSocketEvents) {
            this.socket.addEventListener(eventName, this.handleEvent.bind(this, eventName));
        }

        if (this.reconnectTimeout > 0) {
            this.socket.addEventListener("close", this.autoReconnectHandler.bind(this));
        }
    }

    isConnected() {
        return this.socket !== null;
    }

    disconnect() {
        if (this.socket) {
            this.eventHandlers = {};
            this.socket.removeEventListener('close', this.autoReconnectHandler);
            this.socket.close();
        }

        this.reconnectTimeout = -1;
        this.socket = null;
    }

    send(message: Message) {
        if (this.socket) {
            this.socket.send(JSON.stringify(message));
        }
    }

    on(eventName: string, callback: any) {
        if (this.eventHandlers[eventName]) {
            this.eventHandlers[eventName].push(callback);
        } else {
            this.eventHandlers[eventName] = [callback];
        }
    }

    readyState() {
        if (this.socket) {
            return this.socket.readyState;
        }
    }

    private handleEvent(eventName: string, data: any) {
        if (!this.eventHandlers[eventName]) {
            return;
        }

        for (let handler of this.eventHandlers[eventName]) {
            setTimeout(() => {
                handler(data);
            }, 0);
        }
    }

    private autoReconnectHandler(event: CloseEvent) {
        if (this.reconnectTimeout < 0 || event.code === 1000) {
            return;
        }

        this.socket = null;

        setTimeout(this.heartbeatPollLoop.bind(this), 0);
    }

    private heartbeatPollLoop() {
        const controller = new AbortController();
        setTimeout(() => controller.abort(), 500);

        console.log(`Connection lost. Pinging heartbeat and waiting ${this.reconnectTimeout}ms before repolling.`);

        fetch('/api/heartbeat', { signal: controller.signal })
            .then((res) => {
                if (res.ok) {
                    return res.body;
                }
                throw new Error("Got status: " + res.status);
            })
            .then(() => {
                this.connect();
            })
            .catch(() => {
                setTimeout(this.heartbeatPollLoop.bind(this), this.reconnectTimeout);
            });
    }
}

const enum ReadyState {
    CONNECTING = 0,
    OPEN = 1,
    CLOSING = 2,
    CLOSED = 3
}

export { Socket, ReadyState }