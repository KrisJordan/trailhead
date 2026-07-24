import type { Message } from "../Message";

type WebSocketEventName = keyof WebSocketEventMap;
type EventHandlerCollection = Partial<
    Record<WebSocketEventName, EventListener[]>
>;

const WebSocketEvents: WebSocketEventName[] = [
    "close",
    "error",
    "message",
    "open",
];
const HeartbeatTimeout = 1000;
const TerminalCloseCodes = new Set([
    1000, // Normal closure
    1002, // Protocol error
    1003, // Unsupported data
    1007, // Invalid payload
    1008, // Policy violation
    1009, // Message too large
    1010, // Missing required extension
]);

class Socket {
    socket: WebSocket | null = null
    eventHandlers: EventHandlerCollection = {};
    private reconnectTimer: number | null = null;
    private heartbeatAbortController: AbortController | null = null;
    private heartbeatTimeout: number | null = null;

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
        const socket = new WebSocket(WS_ENDPOINT);
        this.socket = socket;

        for (const eventName of WebSocketEvents) {
            socket.addEventListener(eventName, this.handleEvent.bind(this, eventName));
        }

        if (this.reconnectTimeout >= 0) {
            socket.addEventListener("close", this.autoReconnectHandler);
        }
    }

    isConnected() {
        return this.socket !== null;
    }

    disconnect() {
        this.reconnectTimeout = -1;
        this.cancelReconnect();

        const socket = this.socket;
        this.socket = null;
        this.eventHandlers = {};

        if (socket) {
            socket.removeEventListener("close", this.autoReconnectHandler);
            socket.close();
        }
    }

    send(message: Message) {
        if (this.socket) {
            this.socket.send(JSON.stringify(message));
        }
    }

    on<EventName extends WebSocketEventName>(
        eventName: EventName,
        callback: (data: WebSocketEventMap[EventName]) => void
    ) {
        const handler = callback as unknown as EventListener;
        if (this.eventHandlers[eventName]) {
            this.eventHandlers[eventName].push(handler);
        } else {
            this.eventHandlers[eventName] = [handler];
        }
    }

    readyState() {
        if (this.socket) {
            return this.socket.readyState;
        }
    }

    private handleEvent(eventName: WebSocketEventName, data: Event) {
        if (!this.eventHandlers[eventName]) {
            return;
        }

        for (const handler of this.eventHandlers[eventName]) {
            handler(data);
        }
    }

    private autoReconnectHandler = (event: CloseEvent) => {
        if (event.currentTarget !== this.socket) {
            return;
        }

        this.socket = null;

        if (
            this.reconnectTimeout < 0
            || TerminalCloseCodes.has(event.code)
        ) {
            this.cancelReconnect();
            return;
        }

        this.scheduleReconnect();
    };

    private scheduleReconnect() {
        if (
            this.reconnectTimeout < 0
            || this.reconnectTimer !== null
            || this.heartbeatAbortController !== null
            || this.socket !== null
        ) {
            return;
        }

        console.log(
            `Connection lost. Waiting ${this.reconnectTimeout}ms before checking server availability.`
        );
        this.reconnectTimer = window.setTimeout(() => {
            this.reconnectTimer = null;
            void this.heartbeatPollLoop();
        }, this.reconnectTimeout);
    }

    private async heartbeatPollLoop() {
        if (
            this.reconnectTimeout < 0
            || this.heartbeatAbortController !== null
            || this.socket !== null
        ) {
            return;
        }

        const controller = new AbortController();
        this.heartbeatAbortController = controller;
        this.heartbeatTimeout = window.setTimeout(
            () => controller.abort(),
            HeartbeatTimeout
        );

        try {
            const response = await fetch(
                "/api/heartbeat",
                { signal: controller.signal }
            );
            if (!response.ok) {
                throw new Error("Got status: " + response.status);
            }
        } catch {
            if (!this.finishHeartbeat(controller)) {
                return;
            }
            this.scheduleReconnect();
            return;
        }

        if (!this.finishHeartbeat(controller)) {
            return;
        }

        try {
            this.connect();
        } catch {
            this.scheduleReconnect();
        }
    }

    private finishHeartbeat(controller: AbortController) {
        if (this.heartbeatAbortController !== controller) {
            return false;
        }

        if (this.heartbeatTimeout !== null) {
            window.clearTimeout(this.heartbeatTimeout);
            this.heartbeatTimeout = null;
        }
        this.heartbeatAbortController = null;
        return this.reconnectTimeout >= 0;
    }

    private cancelReconnect() {
        if (this.reconnectTimer !== null) {
            window.clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }
        if (this.heartbeatTimeout !== null) {
            window.clearTimeout(this.heartbeatTimeout);
            this.heartbeatTimeout = null;
        }

        const controller = this.heartbeatAbortController;
        this.heartbeatAbortController = null;
        controller?.abort();
    }
}

const enum ReadyState {
    CONNECTING = 0,
    OPEN = 1,
    CLOSING = 2,
    CLOSED = 3
}

export { Socket, ReadyState }
