import { PayloadAction, createSlice } from "@reduxjs/toolkit";
import { ReadyState } from "../utils/Socket";

export type TestOutcome =
    | "passed"
    | "failed"
    | "skipped"
    | "xfailed"
    | "xpassed"
    | "error"
    | "cancelled";

export type TestPhase = "setup" | "call" | "teardown" | "collection";

export interface CollectedTest {
    node_id: string;
    name: string;
    path?: string;
    line?: number;
    markers?: string[];
}

export interface CapturedTestOutput {
    stdout?: string;
    stderr?: string;
    log?: string;
}

export interface TestFailure {
    phase?: TestPhase;
    message?: string;
    longrepr?: string;
    traceback?: string;
    path?: string;
    line?: number;
}

export interface TestPhaseResult extends CapturedTestOutput {
    phase: TestPhase;
    outcome: TestOutcome;
    duration?: number;
    failure?: TestFailure;
    message?: string;
    longrepr?: string;
    truncated?: string[];
}

export interface TestResult extends CapturedTestOutput {
    node_id: string;
    name?: string;
    path?: string;
    line?: number;
    markers?: string[];
    outcome: TestOutcome;
    duration?: number;
    phase?: TestPhase;
    phases?: TestPhaseResult[];
    failure?: TestFailure;
    longrepr?: string;
}

export type TestSummary = Record<string, number>;

export interface TestRunError {
    kind?: string;
    message: string;
    details?: string;
    phase?: TestPhase;
    path?: string;
    line?: number;
}

export type TestSessionStatus =
    | "idle"
    | "connecting"
    | "collecting"
    | "ready"
    | "running"
    | "cancelling"
    | "finished"
    | "error";

export interface TestsState {
    module: string | null;
    readyState: ReadyState;
    status: TestSessionStatus;
    activeRunId: string | null;
    requestedNodeIds: string[] | null;
    collected: CollectedTest[];
    results: Record<string, TestResult>;
    summary: TestSummary | null;
    duration: number | null;
    exitCode: number | null;
    finishStatus: string | null;
    cancelled: boolean;
    error: TestRunError | null;
    autorun: boolean;
    autorunPending: boolean;
    autorunPaused: boolean;
    autorunWarning: string | null;
    changeRevision: number;
    lastChangedPath: string | null;
}

function initialAutorunPreference(): boolean {
    try {
        return globalThis.localStorage?.getItem("trailhead.pytest.autorun") === "true";
    } catch {
        return false;
    }
}

const initialState: TestsState = {
    module: null,
    readyState: ReadyState.CLOSED,
    status: "idle",
    activeRunId: null,
    requestedNodeIds: null,
    collected: [],
    results: {},
    summary: null,
    duration: null,
    exitCode: null,
    finishStatus: null,
    cancelled: false,
    error: null,
    autorun: initialAutorunPreference(),
    autorunPending: false,
    autorunPaused: false,
    autorunWarning: null,
    changeRevision: 0,
    lastChangedPath: null,
};

const testsSlice = createSlice({
    name: "tests",
    initialState,
    reducers: {
        startTestSession(state, action: PayloadAction<{ module: string }>) {
            state.module = action.payload.module;
            state.readyState = ReadyState.CONNECTING;
            state.status = "connecting";
            state.activeRunId = null;
            state.requestedNodeIds = null;
            state.collected = [];
            state.results = {};
            state.summary = null;
            state.duration = null;
            state.exitCode = null;
            state.finishStatus = null;
            state.cancelled = false;
            state.error = null;
            state.autorunPending = false;
            state.autorunPaused = false;
            state.autorunWarning = null;
        },
        updateTestReadyState(state, action: PayloadAction<ReadyState>) {
            state.readyState = action.payload;
            if (
                action.payload === ReadyState.CLOSED
                && state.status !== "error"
            ) {
                state.status = "idle";
            }
        },
        testCollectionRequested(
            state,
            action: PayloadAction<{ run_id: string }>,
        ) {
            state.activeRunId = action.payload.run_id;
            state.requestedNodeIds = null;
            state.status = "collecting";
            state.error = null;
            state.summary = null;
            state.duration = null;
            state.exitCode = null;
            state.finishStatus = null;
            state.cancelled = false;
        },
        testsCollected(
            state,
            action: PayloadAction<{
                run_id: string;
                tests: CollectedTest[];
            }>,
        ) {
            if (action.payload.run_id !== state.activeRunId) {
                return;
            }
            if (
                (
                    state.status === "running"
                    || state.status === "cancelling"
                )
                && state.requestedNodeIds !== null
            ) {
                const byNodeId = new Map(
                    state.collected.map((test) => [test.node_id, test]),
                );
                for (const test of action.payload.tests) {
                    byNodeId.set(test.node_id, test);
                }
                state.collected = Array.from(byNodeId.values());
            } else {
                state.collected = action.payload.tests;
            }
            if (state.status === "collecting") {
                state.status = "ready";
            }
        },
        testRunRequested(
            state,
            action: PayloadAction<{
                run_id: string;
                node_ids?: string[];
            }>,
        ) {
            state.activeRunId = action.payload.run_id;
            state.requestedNodeIds = action.payload.node_ids ?? null;
            state.status = "running";
            state.results = {};
            state.summary = null;
            state.duration = null;
            state.exitCode = null;
            state.finishStatus = null;
            state.cancelled = false;
            state.error = null;
            state.autorunPending = false;
        },
        testRunStarted(
            state,
            action: PayloadAction<{
                run_id: string;
                node_ids?: string[];
                mode?: "collect" | "run";
            }>,
        ) {
            if (action.payload.run_id !== state.activeRunId) {
                return;
            }
            state.status = action.payload.mode === "collect"
                ? "collecting"
                : "running";
            if (
                action.payload.mode === "run"
                && state.requestedNodeIds !== null
                && action.payload.node_ids
            ) {
                state.requestedNodeIds = action.payload.node_ids;
            }
        },
        testResultReceived(
            state,
            action: PayloadAction<{
                run_id: string;
                result: TestResult;
            }>,
        ) {
            if (
                action.payload.run_id !== state.activeRunId
                || (
                    state.status !== "running"
                    && state.status !== "cancelling"
                )
            ) {
                return;
            }
            state.results[action.payload.result.node_id] =
                action.payload.result;
        },
        testRunFinished(
            state,
            action: PayloadAction<{
                run_id: string;
                summary?: TestSummary;
                duration?: number;
                exit_code?: number | null;
                status?: string;
                cancelled?: boolean;
            }>,
        ) {
            if (action.payload.run_id !== state.activeRunId) {
                return;
            }
            state.status = "finished";
            state.summary = action.payload.summary ?? null;
            state.duration = action.payload.duration ?? null;
            state.exitCode = action.payload.exit_code ?? null;
            state.finishStatus = action.payload.status ?? null;
            state.cancelled = action.payload.cancelled ?? false;
            state.requestedNodeIds = null;
        },
        testRunFailed(
            state,
            action: PayloadAction<{
                run_id: string;
                error: TestRunError;
            }>,
        ) {
            if (action.payload.run_id !== state.activeRunId) {
                return;
            }
            state.error = action.payload.error;
            if (
                state.status !== "collecting"
                && state.status !== "running"
                && state.status !== "cancelling"
            ) {
                state.status = "error";
                state.requestedNodeIds = null;
            }
        },
        testCancelRequested(state) {
            if (
                state.status === "running"
                || state.status === "collecting"
            ) {
                state.status = "cancelling";
            }
            state.autorunPending = false;
        },
        setTestAutorun(state, action: PayloadAction<boolean>) {
            state.autorun = action.payload;
            state.autorunPending = false;
            state.autorunPaused = false;
            state.autorunWarning = null;
        },
        setAutorunPending(state, action: PayloadAction<boolean>) {
            state.autorunPending = action.payload;
        },
        pauseTestAutorun(state, action: PayloadAction<string>) {
            state.autorunPending = false;
            state.autorunPaused = true;
            state.autorunWarning = action.payload;
        },
        resumeTestAutorun(state) {
            state.autorunPaused = false;
            state.autorunWarning = null;
        },
        projectPythonChanged(
            state,
            action: PayloadAction<{ path?: string; kind?: string }>,
        ) {
            state.changeRevision += 1;
            state.lastChangedPath = action.payload.path ?? null;
        },
        endTestSession(state) {
            state.module = null;
            state.readyState = ReadyState.CLOSED;
            state.status = "idle";
            state.activeRunId = null;
            state.requestedNodeIds = null;
            state.autorunPending = false;
        },
    },
});

export const {
    startTestSession,
    updateTestReadyState,
    testCollectionRequested,
    testsCollected,
    testRunRequested,
    testRunStarted,
    testResultReceived,
    testRunFinished,
    testRunFailed,
    testCancelRequested,
    setTestAutorun,
    setAutorunPending,
    pauseTestAutorun,
    resumeTestAutorun,
    projectPythonChanged,
    endTestSession,
} = testsSlice.actions;

export default testsSlice.reducer;
