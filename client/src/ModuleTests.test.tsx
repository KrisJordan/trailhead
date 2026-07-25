import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import {
    ErrorPanel,
    NotRunIndicator,
    ResultDetails,
    Summary,
    TestCountHeading,
    TestOutcomeIndicator,
    TestRow,
    TerminalStatus,
} from "./ModuleTests";

describe("pytest result presentation", () => {
    it.each([
        {
            outcome: "passed" as const,
            label: "Passed",
            icon: "✓",
            color: "bg-success",
        },
        {
            outcome: "failed" as const,
            label: "Failed",
            icon: "✕",
            color: "bg-error",
        },
        {
            outcome: "error" as const,
            label: "Error",
            icon: "✕",
            color: "bg-error",
        },
    ])(
        "renders $outcome as a compact accessible icon",
        ({ outcome, label, icon, color }) => {
            const markup = renderToStaticMarkup(
                <TestOutcomeIndicator outcome={outcome} />,
            );

            expect(markup).toContain(`aria-label="${label}"`);
            expect(markup).toContain(color);
            expect(markup).toContain("rounded-full");
            expect(markup).toContain(`>${icon}</span>`);
            expect(markup).not.toContain(`>${outcome}</span>`);
        },
    );

    it("renders an unrun test as a compact neutral icon", () => {
        const markup = renderToStaticMarkup(<NotRunIndicator />);

        expect(markup).toContain('aria-label="Not run"');
        expect(markup).toContain("bg-base-300");
        expect(markup).toContain("rounded-full");
        expect(markup).toContain(">−</span>");
        expect(markup).not.toContain(">not run</span>");
    });

    it("keeps outcome counts as badges in the run summary", () => {
        const markup = renderToStaticMarkup(
            <Summary
                cancelled={false}
                duration={0.42}
                summary={{ total: 3, passed: 2, failed: 1 }}
            />,
        );

        expect(markup).toContain("2 passed");
        expect(markup).toContain("1 failed");
        expect(markup).toContain("badge-success");
        expect(markup).toContain("badge-error");
        expect(markup).not.toContain("3 tests");
    });

    it("shows each test line on the node id line without a link", () => {
        const markup = renderToStaticMarkup(
            <TestRow
                disabled={false}
                onRun={() => undefined}
                running={false}
                test={{
                    node_id: "test_example.py::test_example",
                    name: "test_example",
                    path: "test_example.py",
                    line: 4,
                }}
            />,
        );

        expect(markup).toContain(
            "test_example.py::test_example · Line 4",
        );
        expect(markup).not.toContain("test_example.py:4");
        expect(markup).not.toMatch(/<a(?:\s|>)/);
    });

    it.each([
        [0, "0 tests"],
        [1, "1 test"],
        [2, "2 tests"],
    ])("uses the collected count as the pane heading", (count, label) => {
        const markup = renderToStaticMarkup(
            <TestCountHeading count={count as number} />,
        );

        expect(markup).toContain(`>${label}</h1>`);
    });

    it("omits phase-summary pills while retaining failure details", () => {
        const markup = renderToStaticMarkup(
            <ResultDetails
                result={{
                    node_id: "test_example.py::test_example",
                    outcome: "failed",
                    phases: [
                        {
                            phase: "setup",
                            outcome: "passed",
                            duration: 0.01,
                        },
                        {
                            phase: "call",
                            outcome: "failed",
                            duration: 0.02,
                            failure: {
                                message: "assert 1 == 2",
                                path: "test_example.py",
                                line: 4,
                            },
                        },
                        {
                            phase: "teardown",
                            outcome: "passed",
                            duration: 0.01,
                        },
                    ],
                }}
            />,
        );

        expect(markup).not.toContain('aria-label="Test phases"');
        expect(markup).not.toContain(">setup<");
        expect(markup).not.toContain(">teardown<");
        expect(markup).toContain(">Line 4</h4>");
        expect(markup).toContain("assert 1 == 2");
        expect(markup).toContain('aria-label="Failed"');
        expect(markup).not.toContain(">failed</span>");
        expect(markup).not.toContain("call phase");
        expect(markup).not.toContain("test_example.py");
        expect(markup).not.toMatch(/<a(?:\s|>)/);
    });

    it.each([
        {
            outcome: "skipped" as const,
            reason: "requires a database",
            panelClass: "bg-warning/5",
        },
        {
            outcome: "xfailed" as const,
            reason: "known issue 123",
            panelClass: "bg-info/5",
        },
    ])(
        "renders a $outcome reason without a red failure panel",
        ({ outcome, reason, panelClass }) => {
            const markup = renderToStaticMarkup(
                <ResultDetails
                    result={{
                        node_id: `test_example.py::test_${outcome}`,
                        outcome,
                        phases: [{
                            phase: "call",
                            outcome,
                            reason,
                            longrepr: `test_example.py:3: ${reason}`,
                            truncated: ["reason"],
                        }],
                    }}
                />,
            );

            expect(markup).toContain(reason);
            expect(markup).toContain(panelClass);
            expect(markup).toContain("details truncated");
            expect(markup).not.toContain("bg-error/5");
        },
    );

    it("renders a non-success terminal status and exit code", () => {
        const markup = renderToStaticMarkup(
            <TerminalStatus exitCode={3} finishStatus="internal_error" />,
        );

        expect(markup).toContain("pytest finished with status");
        expect(markup).toContain("internal error");
        expect(markup).toContain("exit code 3");
        expect(markup).toContain("alert-error");
    });

    it("does not render a terminal warning for a successful run", () => {
        const markup = renderToStaticMarkup(
            <TerminalStatus exitCode={0} finishStatus="passed" />,
        );

        expect(markup).toBe("");
    });

    it("does not render a redundant terminal warning for failed tests", () => {
        const markup = renderToStaticMarkup(
            <TerminalStatus exitCode={1} finishStatus="failed" />,
        );

        expect(markup).toBe("");
    });

    it("labels truncated pytest error details", () => {
        const markup = renderToStaticMarkup(
            <ErrorPanel
                error={{
                    kind: "internal",
                    message: "pytest exited unexpectedly",
                    details: "partial traceback",
                    truncated: ["message", "details"],
                }}
            />,
        );

        expect(markup).toContain("partial traceback");
        expect(markup).toContain("truncated");
        expect(markup).toContain("diagnostic truncated");
    });

    it("renders a concise source frame for collection syntax errors", () => {
        const markup = renderToStaticMarkup(
            <ErrorPanel
                error={{
                    kind: "collection",
                    message: "SyntaxError: invalid syntax",
                    path: "test_broken.py",
                    line: 1,
                    column: 17,
                    end_column: 18,
                    source: "def test_broken(:",
                    details: [
                        "File \"/venv/lib/python/site-packages/_pytest/pathlib.py\"",
                        "File \"<frozen importlib._bootstrap>\"",
                    ].join("\n"),
                }}
            />,
        );

        expect(markup).toContain("Test collection failed");
        expect(markup).toContain(
            "test_broken.py · Line 1, column 17",
        );
        expect(markup).toContain("def test_broken(:");
        expect(markup).toContain("^");
        expect(markup).toContain("SyntaxError: invalid syntax");
        expect(markup).not.toMatch(/<a(?:\s|>)/);
        expect(markup).not.toContain("_pytest/pathlib.py");
        expect(markup).not.toContain("importlib._bootstrap");
    });
});
