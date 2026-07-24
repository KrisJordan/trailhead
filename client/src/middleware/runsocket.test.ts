import { configureStore } from "@reduxjs/toolkit";
import {
    afterEach,
    beforeEach,
    describe,
    expect,
    it,
    vi,
} from "vitest";

interface MockSocketControl {
    emit(eventName: string, event: Event): void;
}

const socketMocks = vi.hoisted(() => ({
    instances: [] as MockSocketControl[],
}));

vi.mock("../utils/Socket", () => ({
    ReadyState: {
        CONNECTING: 0,
        OPEN: 1,
        CLOSING: 2,
        CLOSED: 3,
    },
    Socket: class MockSocket implements MockSocketControl {
        private handlers = new Map<string, Array<(event: Event) => void>>();

        constructor() {
            socketMocks.instances.push(this);
        }

        connect() {
            // Events are emitted explicitly by each test.
        }

        disconnect() {
            // No native socket is opened by this mock.
        }

        send() {
            // No application messages are sent by this test.
        }

        on(eventName: string, callback: (event: Event) => void) {
            const handlers = this.handlers.get(eventName) ?? [];
            handlers.push(callback);
            this.handlers.set(eventName, handlers);
        }

        emit(eventName: string, event: Event) {
            for (const handler of this.handlers.get(eventName) ?? []) {
                handler(event);
            }
        }
    },
}));

import moduleReducer from "../features/module";
import processReducer from "../features/process";
import socketReducer from "../features/socket";
import { PyProcessState } from "../PyProcess";
import { runsocketMiddlewareFactory } from "./runsocket";

const createTestStore = () => configureStore({
    reducer: {
        module: moduleReducer,
        process: processReducer,
        socket: socketReducer,
    },
    middleware: (getDefaultMiddleware) => getDefaultMiddleware()
        .concat(runsocketMiddlewareFactory()),
});

const messageEvent = (type: string, data: object): MessageEvent => ({
    data: JSON.stringify({ type, data }),
} as MessageEvent);

describe("run socket startup ordering", () => {
    beforeEach(() => {
        socketMocks.instances = [];
        vi.stubGlobal("WebSocket", {
            CONNECTING: 0,
            OPEN: 1,
            CLOSING: 2,
            CLOSED: 3,
        });
    });

    afterEach(() => {
        vi.unstubAllGlobals();
    });

    it("retains output that arrives before RUNNING", () => {
        const store = createTestStore();
        store.dispatch({
            type: "runsocket/connect",
            payload: {
                module: "example",
                endpoint: "/ws/example/run",
            },
        });
        const socket = socketMocks.instances[0];
        socket.emit("open", {} as Event);

        socket.emit("message", messageEvent("STDOUT", {
            pid: 42,
            data: "first line\n",
            is_input_prompt: false,
        }));
        socket.emit("message", messageEvent("RUNNING", { pid: 42 }));

        expect(store.getState().process.stdio).toMatchObject([
            {
                type: "stdout_group",
                children: [{ type: "stdout", line: "first line\n" }],
            },
        ]);
    });

    it("reconciles EXIT when a fast process exits before RUNNING", () => {
        const store = createTestStore();
        store.dispatch({
            type: "runsocket/connect",
            payload: {
                module: "example",
                endpoint: "/ws/example/run",
            },
        });
        const socket = socketMocks.instances[0];
        socket.emit("open", {} as Event);

        socket.emit("message", messageEvent("STDOUT", {
            pid: 42,
            data: "fast output\n",
            is_input_prompt: false,
        }));
        socket.emit("message", messageEvent("EXIT", {
            pid: 42,
            returncode: 0,
        }));
        socket.emit("message", messageEvent("RUNNING", { pid: 42 }));

        expect(store.getState().process.active).toMatchObject({
            pid: 42,
            state: PyProcessState.EXITED,
        });
        expect(store.getState().process.stdio).toMatchObject([
            {
                type: "stdout_group",
                children: [{ type: "stdout", line: "fast output\n" }],
            },
        ]);
    });

    it("clears output when a reconnected run opens, before its messages", () => {
        const store = createTestStore();
        store.dispatch({
            type: "runsocket/connect",
            payload: {
                module: "example",
                endpoint: "/ws/example/run",
            },
        });
        const socket = socketMocks.instances[0];
        socket.emit("open", {} as Event);
        socket.emit("message", messageEvent("RUNNING", { pid: 42 }));
        socket.emit("message", messageEvent("STDOUT", {
            pid: 42,
            data: "old run\n",
            is_input_prompt: false,
        }));

        socket.emit("open", {} as Event);

        expect(store.getState().process.stdio).toEqual([]);

        socket.emit("message", messageEvent("STDOUT", {
            pid: 43,
            data: "new run\n",
            is_input_prompt: false,
        }));
        socket.emit("message", messageEvent("RUNNING", { pid: 43 }));

        expect(store.getState().process.stdio).toMatchObject([
            {
                type: "stdout_group",
                children: [{ type: "stdout", line: "new run\n" }],
            },
        ]);
    });
});
