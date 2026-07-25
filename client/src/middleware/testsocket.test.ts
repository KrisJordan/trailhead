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
    path: string;
    sent: Message[];
    emit(eventName: string, event: Event): void;
}

const socketMocks = vi.hoisted(() => ({
    instances: [] as MockSocketControl[],
}));

vi.mock("../utils/Socket", () => {
    return {
        ReadyState: {
            CONNECTING: 0,
            OPEN: 1,
            CLOSING: 2,
            CLOSED: 3,
        },
        Socket: class MockSocket implements MockSocketControl {
            path: string;
            sent: Message[] = [];
            private handlers =
                new Map<string, Array<(event: Event) => void>>();

            constructor(path: string) {
                this.path = path;
                socketMocks.instances.push(this);
            }

            connect() {
                // Tests explicitly emit the open event.
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
    };
});

import {
    projectPythonChanged,
    resumeTestAutorun,
    setTestAutorun,
} from "../features/tests";
import testsReducer from "../features/tests";
import { testsocketMiddlewareFactory } from "./testsocket";

const createTestStore = () => configureStore({
    reducer: {
        tests: testsReducer,
    },
    middleware: (getDefaultMiddleware) => getDefaultMiddleware()
        .concat(testsocketMiddlewareFactory()),
});

const messageEvent = (type: string, data: object): MessageEvent => ({
    data: JSON.stringify({ type, data }),
} as MessageEvent);

function connectAndOpen() {
    const store = createTestStore();
    store.dispatch({
        type: "testsocket/connect",
        payload: {
            module: "test_example",
            endpoint: "/ws/test_example/tests",
        },
    });
    const socket = socketMocks.instances[0];
    socket.emit("open", {} as Event);
    return { socket, store };
}

function finishCurrentOperation(
    socket: MockSocketControl,
    store: ReturnType<typeof createTestStore>,
) {
    const runId = store.getState().tests.activeRunId;
    expect(runId).toBeTruthy();
    socket.emit("message", messageEvent("TEST_RUN_FINISHED", {
        run_id: runId,
        exit_code: 0,
        status: "passed",
        duration: 0.01,
        summary: { total: 0, passed: 0 },
        cancelled: false,
    }));
}

describe("pytest socket middleware", () => {
    beforeEach(() => {
        socketMocks.instances = [];
    });

    afterEach(() => {
        vi.useRealTimers();
        vi.unstubAllGlobals();
    });

    it("connects to the module endpoint and collects after open", () => {
        const { socket, store } = connectAndOpen();

        expect(socket.path).toBe("/ws/test_example/tests");
        expect(socket.sent).toHaveLength(1);
        expect(socket.sent[0]).toMatchObject({
            type: "TEST_COLLECT",
            data: { run_id: expect.any(String) },
        });
        expect(store.getState().tests.status).toBe("collecting");
    });

    it("normalizes collected tests and phase-level results", () => {
        const { socket, store } = connectAndOpen();
        const collectRunId = store.getState().tests.activeRunId;
        socket.emit("message", messageEvent("TEST_RUN_STARTED", {
            run_id: collectRunId,
            mode: "collect",
            node_ids: [],
            pid: 123,
        }));
        socket.emit("message", messageEvent("TESTS_COLLECTED", {
            run_id: collectRunId,
            tests: [{
                node_id: "test_example.py::test_value",
                name: "test_value",
                path: "test_example.py",
                line: 4,
                markers: ["unit"],
            }],
        }));
        finishCurrentOperation(socket, store);

        store.dispatch({
            type: "testsocket/run",
            payload: { node_ids: ["test_example.py::test_value"] },
        });
        const runId = store.getState().tests.activeRunId;
        socket.emit("message", messageEvent("TEST_RUN_STARTED", {
            run_id: runId,
            mode: "run",
            node_ids: ["test_example.py::test_value"],
            pid: 124,
        }));
        socket.emit("message", messageEvent("TEST_RESULT", {
            run_id: runId,
            test: {
                node_id: "test_example.py::test_value",
                name: "test_value",
                path: "test_example.py",
                line: 4,
                markers: ["unit"],
                outcome: "failed",
                duration: 0.02,
                phases: [{
                    phase: "call",
                    outcome: "failed",
                    duration: 0.02,
                    reason: "known defect",
                    message: "assert 1 == 2",
                    longrepr: "E assert 1 == 2",
                    stdout: "value was 1\n",
                    stderr: "",
                    log: "debug record\n",
                    truncated: ["stdout"],
                }],
            },
        }));

        expect(
            store.getState().tests.results[
                "test_example.py::test_value"
            ],
        ).toMatchObject({
            outcome: "failed",
            duration: 0.02,
            phases: [{
                phase: "call",
                reason: "known defect",
                message: "assert 1 == 2",
                longrepr: "E assert 1 == 2",
                stdout: "value was 1\n",
                log: "debug record\n",
                truncated: ["stdout"],
            }],
        });
    });

    it("preserves truncation metadata from pytest errors", () => {
        const { socket, store } = connectAndOpen();
        const runId = store.getState().tests.activeRunId;

        socket.emit("message", messageEvent("TEST_ERROR", {
            run_id: runId,
            kind: "collection",
            message: "Collection output exceeded the limit",
            details: "partial collection traceback",
            truncated: ["details"],
        }));

        expect(store.getState().tests.error).toEqual({
            kind: "collection",
            message: "Collection output exceeded the limit",
            details: "partial collection traceback",
            phase: undefined,
            path: undefined,
            line: undefined,
            column: undefined,
            end_column: undefined,
            source: undefined,
            truncated: ["details"],
        });
    });

    it("preserves structured syntax-error diagnostics", () => {
        const { socket, store } = connectAndOpen();
        const runId = store.getState().tests.activeRunId;

        socket.emit("message", messageEvent("TEST_ERROR", {
            run_id: runId,
            kind: "collection",
            message: "SyntaxError: invalid syntax",
            path: "test_broken.py",
            line: 1,
            column: 17,
            end_column: 18,
            source: "def test_broken(:",
            details: [
                "test_broken.py:1:17",
                "def test_broken(:",
                "                ^",
                "SyntaxError: invalid syntax",
            ].join("\n"),
        }));

        expect(store.getState().tests.error).toMatchObject({
            kind: "collection",
            message: "SyntaxError: invalid syntax",
            path: "test_broken.py",
            line: 1,
            column: 17,
            end_column: 18,
            source: "def test_broken(:",
        });
    });

    it("does not send a second operation while pytest is busy", () => {
        const { socket, store } = connectAndOpen();
        const collectRunId = store.getState().tests.activeRunId;
        socket.emit("message", messageEvent("TESTS_COLLECTED", {
            run_id: collectRunId,
            tests: [{
                node_id: "test_example.py::test_value",
                name: "test_value",
            }],
        }));

        store.dispatch({ type: "testsocket/run" });
        store.dispatch({ type: "testsocket/collect" });

        expect(socket.sent.map((message) => message.type)).toEqual([
            "TEST_COLLECT",
        ]);
        expect(store.getState().tests.status).toBe("collecting");
    });

    it("debounces changes and coalesces one rerun during a run", () => {
        vi.useFakeTimers();
        const { socket, store } = connectAndOpen();
        finishCurrentOperation(socket, store);
        store.dispatch(setTestAutorun(true));

        store.dispatch(projectPythonChanged({
            kind: "file_modified",
            path: "src/example.py",
        }));
        vi.advanceTimersByTime(399);
        expect(socket.sent.filter(
            (message) => message.type === "TEST_RUN",
        )).toHaveLength(0);
        vi.advanceTimersByTime(1);
        expect(socket.sent.filter(
            (message) => message.type === "TEST_RUN",
        )).toHaveLength(1);

        store.dispatch(projectPythonChanged({
            kind: "file_modified",
            path: "src/example.py",
        }));
        store.dispatch(projectPythonChanged({
            kind: "file_modified",
            path: "src/example.py",
        }));
        vi.advanceTimersByTime(400);
        expect(store.getState().tests.autorunPending).toBe(true);
        expect(socket.sent.filter(
            (message) => message.type === "TEST_RUN",
        )).toHaveLength(1);

        finishCurrentOperation(socket, store);
        expect(socket.sent.filter(
            (message) => message.type === "TEST_RUN",
        )).toHaveLength(2);
        expect(store.getState().tests.autorunPending).toBe(false);
    });

    it("lets a manual run consume a pending debounce", () => {
        vi.useFakeTimers();
        const { socket, store } = connectAndOpen();
        finishCurrentOperation(socket, store);
        store.dispatch(setTestAutorun(true));

        store.dispatch(projectPythonChanged({
            kind: "file_modified",
            path: "src/example.py",
        }));
        vi.advanceTimersByTime(200);
        store.dispatch({ type: "testsocket/run" });
        vi.advanceTimersByTime(400);

        expect(socket.sent.filter(
            (message) => message.type === "TEST_RUN",
        )).toHaveLength(1);
    });

    it("waits for a newer debounce before consuming a queued autorun", () => {
        vi.useFakeTimers();
        const { socket, store } = connectAndOpen();
        finishCurrentOperation(socket, store);
        store.dispatch(setTestAutorun(true));

        store.dispatch(projectPythonChanged({
            kind: "file_modified",
            path: "src/first.py",
        }));
        vi.advanceTimersByTime(400);

        store.dispatch(projectPythonChanged({
            kind: "file_modified",
            path: "src/queued.py",
        }));
        vi.advanceTimersByTime(400);
        expect(store.getState().tests.autorunPending).toBe(true);

        store.dispatch(projectPythonChanged({
            kind: "file_modified",
            path: "src/newest.py",
        }));
        finishCurrentOperation(socket, store);

        expect(socket.sent.filter(
            (message) => message.type === "TEST_RUN",
        )).toHaveLength(1);
        expect(store.getState().tests.autorunPending).toBe(true);

        vi.advanceTimersByTime(400);
        expect(socket.sent.filter(
            (message) => message.type === "TEST_RUN",
        )).toHaveLength(2);
        expect(store.getState().tests.autorunPending).toBe(false);

        finishCurrentOperation(socket, store);
        expect(socket.sent.filter(
            (message) => message.type === "TEST_RUN",
        )).toHaveLength(2);
    });

    it("cancels a pending debounce when autorun is disabled", () => {
        vi.useFakeTimers();
        const { socket, store } = connectAndOpen();
        finishCurrentOperation(socket, store);
        store.dispatch(setTestAutorun(true));
        store.dispatch(projectPythonChanged({
            kind: "file_modified",
            path: "src/example.py",
        }));

        store.dispatch(setTestAutorun(false));
        vi.advanceTimersByTime(500);

        expect(socket.sent.filter(
            (message) => message.type === "TEST_RUN",
        )).toHaveLength(0);
    });

    it("pauses autorun after repeated rapid reruns", () => {
        vi.useFakeTimers();
        const { socket, store } = connectAndOpen();
        finishCurrentOperation(socket, store);
        store.dispatch(setTestAutorun(true));

        for (let index = 0; index < 6; index += 1) {
            store.dispatch(projectPythonChanged({
                kind: "file_modified",
                path: `src/example_${index}.py`,
            }));
            vi.advanceTimersByTime(400);
            if (index < 5) {
                finishCurrentOperation(socket, store);
            }
        }

        expect(socket.sent.filter(
            (message) => message.type === "TEST_RUN",
        )).toHaveLength(5);
        expect(store.getState().tests.autorunPaused).toBe(true);
        expect(store.getState().tests.autorunWarning).toContain(
            "repeated rapid changes",
        );

        store.dispatch(resumeTestAutorun());
        store.dispatch({
            type: "testsocket/run",
            payload: { source: "autorun" },
        });
        expect(socket.sent.filter(
            (message) => message.type === "TEST_RUN",
        )).toHaveLength(6);
        expect(store.getState().tests.autorunPaused).toBe(false);
    });
});
