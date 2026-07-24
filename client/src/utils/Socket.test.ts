import {
    afterEach,
    beforeEach,
    describe,
    expect,
    it,
    vi,
} from "vitest";

import { Socket } from "./Socket";

class MockWebSocket {
    static readonly CONNECTING = 0;
    static readonly OPEN = 1;
    static readonly CLOSING = 2;
    static readonly CLOSED = 3;
    static constructorFailures = 0;
    static instances: MockWebSocket[] = [];

    readonly url: string;
    readyState: number = WebSocket.CONNECTING;
    private listeners = new Map<
        string,
        Set<EventListenerOrEventListenerObject>
    >();

    constructor(url: string | URL) {
        if (MockWebSocket.constructorFailures > 0) {
            MockWebSocket.constructorFailures -= 1;
            throw new Error("WebSocket construction failed");
        }
        this.url = url.toString();
        MockWebSocket.instances.push(this);
    }

    addEventListener(
        type: string,
        listener: EventListenerOrEventListenerObject | null
    ) {
        if (listener === null) {
            return;
        }
        const listeners = this.listeners.get(type) ?? new Set();
        listeners.add(listener);
        this.listeners.set(type, listeners);
    }

    removeEventListener(
        type: string,
        listener: EventListenerOrEventListenerObject | null
    ) {
        if (listener !== null) {
            this.listeners.get(type)?.delete(listener);
        }
    }

    send() {
        // The reconnect tests do not exchange application messages.
    }

    close(code = 1000, reason = "") {
        this.closeFromServer(code, reason);
    }

    closeFromServer(code: number, reason = "") {
        if (this.readyState === WebSocket.CLOSED) {
            return;
        }
        this.readyState = WebSocket.CLOSED;
        const event = {
            code,
            currentTarget: this,
            reason,
            target: this,
            type: "close",
            wasClean: code !== 1006,
        } as unknown as CloseEvent;
        for (const listener of this.listeners.get("close") ?? []) {
            if (typeof listener === "function") {
                listener.call(this, event);
            } else {
                listener.handleEvent(event);
            }
        }
    }
}

const heartbeatOk = { ok: true, status: 200 } as Response;

describe("Socket reconnect behavior", () => {
    const fetchMock = vi.fn();

    beforeEach(() => {
        vi.useFakeTimers();
        MockWebSocket.constructorFailures = 0;
        MockWebSocket.instances = [];
        fetchMock.mockReset();
        vi.stubGlobal("window", {
            location: {
                host: "127.0.0.1:1110",
                protocol: "http:",
            },
            setTimeout,
            clearTimeout,
        });
        vi.stubGlobal("WebSocket", MockWebSocket);
        vi.stubGlobal("fetch", fetchMock);
        vi.spyOn(console, "log").mockImplementation(() => undefined);
    });

    afterEach(() => {
        vi.useRealTimers();
        vi.restoreAllMocks();
        vi.unstubAllGlobals();
    });

    it.each([
        [1000, "Normal closure"],
        [1008, "Module not found"],
    ])("does not retry terminal close code %i", async (code, reason) => {
        const socket = new Socket("/ws/missing/run", 1000);
        socket.connect();

        MockWebSocket.instances[0].closeFromServer(code, reason);
        await vi.runAllTimersAsync();

        expect(fetchMock).not.toHaveBeenCalled();
        expect(MockWebSocket.instances).toHaveLength(1);
    });

    it("waits the reconnect interval even when heartbeat is healthy", async () => {
        fetchMock.mockResolvedValue(heartbeatOk);
        const socket = new Socket("/ws/example/run", 1000);
        socket.connect();

        MockWebSocket.instances[0].closeFromServer(1006);
        await vi.advanceTimersByTimeAsync(999);

        expect(fetchMock).not.toHaveBeenCalled();
        expect(MockWebSocket.instances).toHaveLength(1);

        await vi.advanceTimersByTimeAsync(1);

        expect(fetchMock).toHaveBeenCalledTimes(1);
        expect(MockWebSocket.instances).toHaveLength(2);

        MockWebSocket.instances[1].closeFromServer(1006);
        await vi.advanceTimersByTimeAsync(999);

        expect(fetchMock).toHaveBeenCalledTimes(1);
        expect(MockWebSocket.instances).toHaveLength(2);

        await vi.advanceTimersByTimeAsync(1);

        expect(fetchMock).toHaveBeenCalledTimes(2);
        expect(MockWebSocket.instances).toHaveLength(3);
    });

    it("keeps retry pacing when WebSocket construction throws", async () => {
        fetchMock.mockResolvedValue(heartbeatOk);
        const socket = new Socket("/ws/example/run", 1000);
        socket.connect();

        MockWebSocket.instances[0].closeFromServer(1006);
        MockWebSocket.constructorFailures = 1;
        await vi.advanceTimersByTimeAsync(1000);

        expect(fetchMock).toHaveBeenCalledTimes(1);
        expect(MockWebSocket.instances).toHaveLength(1);

        await vi.advanceTimersByTimeAsync(999);
        expect(fetchMock).toHaveBeenCalledTimes(1);

        await vi.advanceTimersByTimeAsync(1);
        expect(fetchMock).toHaveBeenCalledTimes(2);
        expect(MockWebSocket.instances).toHaveLength(2);
    });

    it("cancels a queued reconnect when disconnected", async () => {
        fetchMock.mockResolvedValue(heartbeatOk);
        const socket = new Socket("/ws/example/repl", 1000);
        socket.connect();

        MockWebSocket.instances[0].closeFromServer(1006);
        socket.disconnect();
        await vi.runAllTimersAsync();

        expect(fetchMock).not.toHaveBeenCalled();
        expect(MockWebSocket.instances).toHaveLength(1);
    });

    it("ignores a heartbeat that settles after disconnect", async () => {
        let resolveHeartbeat: (response: Response) => void = () => undefined;
        fetchMock.mockReturnValue(new Promise<Response>((resolve) => {
            resolveHeartbeat = resolve;
        }));
        const socket = new Socket("/ws/example/repl", 1000);
        socket.connect();

        MockWebSocket.instances[0].closeFromServer(1006);
        await vi.advanceTimersByTimeAsync(1000);
        expect(fetchMock).toHaveBeenCalledTimes(1);

        socket.disconnect();
        resolveHeartbeat(heartbeatOk);
        await vi.runAllTimersAsync();

        expect(MockWebSocket.instances).toHaveLength(1);
    });
});
