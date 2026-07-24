import { describe, expect, it } from "vitest";
import reducer, {
    startTestSession,
    testCollectionRequested,
    testResultReceived,
    testRunFailed,
    testRunFinished,
    testRunRequested,
    testRunStarted,
    testsCollected,
} from "./tests";

const collected = (nodeId: string, name = nodeId) => ({
    node_id: nodeId,
    name,
});

describe("tests reducer", () => {
    it("preserves a collection diagnostic and partial items through finish", () => {
        let state = reducer(
            undefined,
            startTestSession({ module: "test_example" }),
        );
        state = reducer(
            state,
            testCollectionRequested({ run_id: "collect-1" }),
        );
        state = reducer(
            state,
            testRunStarted({
                run_id: "collect-1",
                mode: "collect",
                node_ids: [],
            }),
        );
        expect(state.status).toBe("collecting");

        state = reducer(
            state,
            testRunFailed({
                run_id: "collect-1",
                error: {
                    kind: "collection",
                    message: "ImportError while importing test module",
                },
            }),
        );
        state = reducer(
            state,
            testsCollected({
                run_id: "collect-1",
                tests: [collected("test_example.py::test_before_error")],
            }),
        );
        expect(state.status).toBe("collecting");
        state = reducer(
            state,
            testRunFinished({
                run_id: "collect-1",
                exit_code: 2,
                status: "collection_error",
                summary: { total: 1, error: 1 },
            }),
        );

        expect(state.status).toBe("finished");
        expect(state.error).toMatchObject({
            kind: "collection",
            message: "ImportError while importing test module",
        });
        expect(state.collected).toHaveLength(1);
        expect(state.exitCode).toBe(2);
    });

    it("leaves a rejected command in an actionable error state", () => {
        let state = reducer(
            undefined,
            startTestSession({ module: "test_example" }),
        );
        state = reducer(
            state,
            testRunRequested({ run_id: "run-1" }),
        );
        state = reducer(
            state,
            testRunFailed({
                run_id: "run-1",
                error: {
                    kind: "validation",
                    message: "Selected tests must come from the latest collection",
                },
            }),
        );

        expect(state.status).toBe("error");
        expect(state.requestedNodeIds).toBeNull();
        expect(state.error?.message).toContain("latest collection");
    });

    it("does not replace the full collection during a run-one request", () => {
        let state = reducer(
            undefined,
            startTestSession({ module: "test_example" }),
        );
        state = reducer(
            state,
            testCollectionRequested({ run_id: "collect-1" }),
        );
        state = reducer(
            state,
            testsCollected({
                run_id: "collect-1",
                tests: [
                    collected("test_example.py::test_one", "test_one"),
                    collected("test_example.py::test_two", "test_two"),
                ],
            }),
        );
        state = reducer(
            state,
            testRunRequested({
                run_id: "run-one",
                node_ids: ["test_example.py::test_one"],
            }),
        );
        state = reducer(
            state,
            testsCollected({
                run_id: "run-one",
                tests: [
                    collected(
                        "test_example.py::test_one",
                        "test_one[updated]",
                    ),
                ],
            }),
        );

        expect(state.collected.map((test) => test.node_id)).toEqual([
            "test_example.py::test_one",
            "test_example.py::test_two",
        ]);
        expect(state.collected[0].name).toBe("test_one[updated]");
    });

    it("refreshes the full collection during a run-all request", () => {
        let state = reducer(
            undefined,
            startTestSession({ module: "test_example" }),
        );
        state = reducer(
            state,
            testCollectionRequested({ run_id: "collect-1" }),
        );
        state = reducer(
            state,
            testsCollected({
                run_id: "collect-1",
                tests: [collected("test_example.py::test_old", "test_old")],
            }),
        );
        state = reducer(
            state,
            testRunRequested({ run_id: "run-all" }),
        );
        state = reducer(
            state,
            testsCollected({
                run_id: "run-all",
                tests: [collected("test_example.py::test_new", "test_new")],
            }),
        );

        expect(state.collected).toEqual([
            collected("test_example.py::test_new", "test_new"),
        ]);
    });

    it("clears stale results when a new collection starts", () => {
        let state = reducer(
            undefined,
            startTestSession({ module: "test_example" }),
        );
        state = reducer(
            state,
            testRunRequested({ run_id: "run-1" }),
        );
        state = reducer(
            state,
            testResultReceived({
                run_id: "run-1",
                result: {
                    node_id: "test_example.py::test_old",
                    outcome: "failed",
                },
            }),
        );
        state = reducer(
            state,
            testRunFinished({
                run_id: "run-1",
                summary: { total: 1, failed: 1 },
                exit_code: 1,
                status: "failed",
            }),
        );

        state = reducer(
            state,
            testCollectionRequested({ run_id: "collect-2" }),
        );

        expect(state.status).toBe("collecting");
        expect(state.results).toEqual({});
        expect(state.summary).toBeNull();
        expect(state.exitCode).toBeNull();
        expect(state.finishStatus).toBeNull();
    });

    it("adds a visible row for a result omitted from the collection", () => {
        let state = reducer(
            undefined,
            startTestSession({ module: "test_example" }),
        );
        state = reducer(
            state,
            testRunRequested({ run_id: "run-1" }),
        );
        state = reducer(
            state,
            testResultReceived({
                run_id: "run-1",
                result: {
                    node_id: "test_example.py::test_hidden[param]",
                    name: "test_hidden[param]",
                    path: "test_example.py",
                    line: 17,
                    markers: ["parametrize"],
                    outcome: "failed",
                },
            }),
        );

        expect(state.collected).toContainEqual({
            node_id: "test_example.py::test_hidden[param]",
            name: "test_hidden[param]",
            path: "test_example.py",
            line: 17,
            markers: ["parametrize"],
        });
        expect(
            state.results["test_example.py::test_hidden[param]"].outcome,
        ).toBe("failed");
    });

    it("ignores every result event from a stale run", () => {
        let state = reducer(
            undefined,
            startTestSession({ module: "test_example" }),
        );
        state = reducer(
            state,
            testRunRequested({ run_id: "current" }),
        );

        state = reducer(
            state,
            testRunStarted({ run_id: "stale", mode: "run" }),
        );
        state = reducer(
            state,
            testsCollected({
                run_id: "stale",
                tests: [collected("stale.py::test_stale")],
            }),
        );
        state = reducer(
            state,
            testResultReceived({
                run_id: "stale",
                result: {
                    node_id: "stale.py::test_stale",
                    outcome: "failed",
                },
            }),
        );
        state = reducer(
            state,
            testRunFailed({
                run_id: "stale",
                error: { message: "stale error" },
            }),
        );
        state = reducer(
            state,
            testRunFinished({
                run_id: "stale",
                exit_code: 1,
                summary: { failed: 1 },
            }),
        );

        expect(state.activeRunId).toBe("current");
        expect(state.status).toBe("running");
        expect(state.collected).toEqual([]);
        expect(state.results).toEqual({});
        expect(state.error).toBeNull();
        expect(state.summary).toBeNull();
    });

    it("stores phase-level failure and captured output for the current run", () => {
        let state = reducer(
            undefined,
            startTestSession({ module: "test_example" }),
        );
        state = reducer(
            state,
            testRunRequested({ run_id: "run-1" }),
        );
        state = reducer(
            state,
            testResultReceived({
                run_id: "run-1",
                result: {
                    node_id: "test_example.py::test_value",
                    outcome: "failed",
                    duration: 0.02,
                    phases: [{
                        phase: "call",
                        outcome: "failed",
                        message: "assert 1 == 2",
                        longrepr: "E assert 1 == 2",
                        stdout: "debug value: 1\n",
                    }],
                },
            }),
        );

        expect(
            state.results["test_example.py::test_value"],
        ).toMatchObject({
            outcome: "failed",
            phases: [{
                phase: "call",
                message: "assert 1 == 2",
                stdout: "debug value: 1\n",
            }],
        });
    });
});
