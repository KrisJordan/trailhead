import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import {
    ErrorPanel,
    ResultDetails,
    TerminalStatus,
} from "./ModuleTests";

describe("pytest result presentation", () => {
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
});
