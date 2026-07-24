import { configureStore } from "@reduxjs/toolkit";
import {
    afterEach,
    beforeEach,
    describe,
    expect,
    it,
    vi,
} from "vitest";
import type { Message } from "../Message";

interface MockSocketControl {
    sent: Message[];
    emit(eventName: string, event: Event): void;
}

const mocks = vi.hoisted(() => ({
    navigate: vi.fn(),
    routerState: {
        location: {
            pathname: "/module/test_example/tests",
        },
    },
    sockets: [] as MockSocketControl[],
}));

vi.mock("../routes", () => ({
    default: {
        navigate: mocks.navigate,
        state: mocks.routerState,
    },
}));

vi.mock("../utils/Socket", () => ({
    ReadyState: {
        CONNECTING: 0,
        OPEN: 1,
        CLOSING: 2,
        CLOSED: 3,
    },
    Socket: class MockSocket implements MockSocketControl {
        sent: Message[] = [];
        private handlers =
            new Map<string, Array<(event: Event) => void>>();

        constructor() {
            mocks.sockets.push(this);
        }

        connect() {
            // Tests emit socket events explicitly.
        }

        disconnect() {
            this.handlers.clear();
        }

        send(message: Message) {
            this.sent.push(message);
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

import filesReducer from "../features/files";
import socketReducer from "../features/socket";
import testsReducer from "../features/tests";
import { websocketMiddlewareFactory } from "./websocket";

const messageEvent = (type: string, data: object): MessageEvent => ({
    data: JSON.stringify({ type, data }),
} as MessageEvent);

const createTestStore = () => configureStore({
    reducer: {
        files: filesReducer,
        socket: socketReducer,
        tests: testsReducer,
    },
    middleware: (getDefaultMiddleware) => getDefaultMiddleware()
        .concat(websocketMiddlewareFactory()),
});

describe("project file socket middleware", () => {
    beforeEach(() => {
        mocks.navigate.mockReset();
        mocks.routerState.location.pathname = "/module/test_example/tests";
        mocks.sockets = [];
        vi.stubGlobal("WebSocket", {
            CONNECTING: 0,
            OPEN: 1,
            CLOSING: 2,
            CLOSED: 3,
        });
        vi.spyOn(console, "log").mockImplementation(() => undefined);
    });

    afterEach(() => {
        vi.restoreAllMocks();
        vi.unstubAllGlobals();
    });

    it("publishes Python changes without reloading the Tests route", () => {
        const store = createTestStore();
        store.dispatch({ type: "socket/connect" });
        const socket = mocks.sockets[0];

        socket.emit("message", messageEvent("file_modified", {
            path: "./src/example.py",
        }));

        expect(store.getState().tests).toMatchObject({
            changeRevision: 1,
            lastChangedPath: "./src/example.py",
        });
        expect(mocks.navigate).not.toHaveBeenCalled();
    });

    it("preserves existing reload behavior outside Tests", () => {
        mocks.routerState.location.pathname = "/module/example/run";
        const store = createTestStore();
        store.dispatch({ type: "socket/connect" });

        mocks.sockets[0].emit("message", messageEvent("file_modified", {
            path: "./example.py",
        }));

        expect(store.getState().tests.changeRevision).toBe(1);
        expect(mocks.navigate).toHaveBeenCalledWith(".", { replace: true });
    });

    it("publishes create, move, and delete events and refreshes the tree", () => {
        const store = createTestStore();
        store.dispatch({ type: "socket/connect" });
        const socket = mocks.sockets[0];

        for (const type of [
            "file_created",
            "file_moved",
            "file_deleted",
        ]) {
            socket.emit("message", messageEvent(type, {
                path: "./test_example.py",
            }));
        }

        expect(store.getState().tests.changeRevision).toBe(3);
        expect(socket.sent).toEqual([
            { type: "LS", data: { path: "/" } },
            { type: "LS", data: { path: "/" } },
            { type: "LS", data: { path: "/" } },
        ]);
    });
});
