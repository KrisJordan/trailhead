import { useEffect, type ReactNode } from "react";
import { useDispatch, useSelector } from "react-redux";
import { RootState } from "./app/store";
import {
    CapturedTestOutput,
    CollectedTest,
    TestOutcome,
    TestPhaseResult,
    TestResult,
    TestRunError,
    TestSummary,
    TestsState,
    normalizeEditorUrl,
    resumeTestAutorun,
    setTestAutorun,
} from "./features/tests";
import { ModuleState } from "./features/module";
import { ReadyState } from "./utils/Socket";

const outcomeOrder: TestOutcome[] = [
    "passed",
    "failed",
    "error",
    "skipped",
    "xfailed",
    "xpassed",
    "cancelled",
];

const outcomeClasses: Record<TestOutcome, string> = {
    passed: "badge-success",
    failed: "badge-error text-white",
    error: "badge-error text-white",
    skipped: "badge-warning",
    xfailed: "badge-info",
    xpassed: "badge-warning",
    cancelled: "badge-neutral text-white",
};

export function SourceLink({
    children,
    editorUrl,
    label,
    className,
}: {
    children: ReactNode;
    editorUrl?: string;
    label: string;
    className?: string;
}) {
    const safeEditorUrl = normalizeEditorUrl(editorUrl);
    if (!safeEditorUrl) {
        return <span className={className}>{children}</span>;
    }
    return (
        <a
            aria-label={`Open ${label} in VS Code`}
            className={`link ${className ?? ""}`}
            href={safeEditorUrl}
            title="Open in VS Code"
        >
            {children}
        </a>
    );
}

function formatDuration(duration?: number | null): string | null {
    if (duration === undefined || duration === null) {
        return null;
    }
    if (duration < 1) {
        return `${Math.round(duration * 1000)} ms`;
    }
    return `${duration.toFixed(2)} s`;
}

function deriveTestSummary(
    results: Record<string, TestResult>,
): TestSummary {
    const summary: TestSummary = { total: Object.keys(results).length };
    for (const result of Object.values(results)) {
        summary[result.outcome] = (summary[result.outcome] ?? 0) + 1;
    }
    return summary;
}

export function TestOutcomeIndicator({
    outcome,
}: {
    outcome: TestOutcome;
}) {
    if (outcome === "passed") {
        return (
            <span
                aria-label="Passed"
                className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-success text-xs font-bold leading-none text-white"
                role="img"
                title="Passed"
            >
                <span aria-hidden="true">✓</span>
            </span>
        );
    }
    if (outcome === "failed" || outcome === "error") {
        const label = outcome === "failed" ? "Failed" : "Error";
        return (
            <span
                aria-label={label}
                className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-error text-xs font-bold leading-none text-white"
                role="img"
                title={label}
            >
                <span aria-hidden="true">✕</span>
            </span>
        );
    }
    return (
        <span className={`badge badge-sm ${outcomeClasses[outcome]}`}>
            {outcome}
        </span>
    );
}

export function Summary({
    summary,
    duration,
    cancelled,
}: {
    summary: TestSummary;
    duration: number | null;
    cancelled: boolean;
}) {
    const total = summary.total;
    return (
        <div
            className="flex flex-wrap items-center gap-2"
            aria-label="Test run summary"
        >
            {typeof total === "number" && (
                <span className="font-semibold">
                    {total} {total === 1 ? "test" : "tests"}
                </span>
            )}
            {outcomeOrder.map((outcome) => {
                const count = summary[outcome] ?? 0;
                return count > 0
                    ? (
                        <span
                            className={`badge ${outcomeClasses[outcome]}`}
                            key={outcome}
                        >
                            {count} {outcome}
                        </span>
                    )
                    : null;
            })}
            {cancelled && (
                <span className="badge badge-neutral text-white">
                    run cancelled
                </span>
            )}
            {formatDuration(duration) && (
                <span className="text-sm opacity-70">
                    in {formatDuration(duration)}
                </span>
            )}
        </div>
    );
}

function Output({
    label,
    text,
    truncated,
}: {
    label: string;
    text?: string;
    truncated?: boolean;
}) {
    if (!text) {
        return null;
    }
    return (
        <details className="collapse collapse-arrow border border-base-300">
            <summary className="collapse-title min-h-0 py-2 font-medium">
                {label}
                {truncated && (
                    <span className="badge badge-warning badge-sm ml-2">
                        truncated
                    </span>
                )}
            </summary>
            <div className="collapse-content">
                <pre className="overflow-x-auto whitespace-pre-wrap break-words rounded bg-neutral p-3 text-sm text-neutral-content">
                    {text}
                </pre>
            </div>
        </details>
    );
}

function CapturedOutput({
    output,
    truncated = [],
}: {
    output: CapturedTestOutput;
    truncated?: string[];
}) {
    return (
        <div className="grid gap-2">
            <Output
                label="Captured stdout"
                text={output.stdout}
                truncated={truncated.includes("stdout")}
            />
            <Output
                label="Captured stderr"
                text={output.stderr}
                truncated={truncated.includes("stderr")}
            />
            <Output
                label="Captured log"
                text={output.log}
                truncated={truncated.includes("log")}
            />
        </div>
    );
}

function phasePanelClasses(outcome: TestOutcome): string {
    switch (outcome) {
        case "failed":
        case "error":
            return "border-error/40 bg-error/5";
        case "skipped":
        case "xpassed":
            return "border-warning/40 bg-warning/5";
        case "xfailed":
            return "border-info/40 bg-info/5";
        default:
            return "border-base-300 bg-base-200/30";
    }
}

function PhaseDetail({
    phase,
    result,
}: {
    phase: TestPhaseResult;
    result: TestResult;
}) {
    const failure = phase.failure;
    const isFailure = phase.outcome === "failed"
        || phase.outcome === "error";
    const message = isFailure
        ? failure?.message ?? phase.message
        : phase.reason ?? phase.message ?? failure?.message;
    const longrepr = failure?.longrepr ?? phase.longrepr;
    const traceback = failure?.traceback;
    const path = failure?.path ?? result.path;
    const line = failure?.line ?? result.line;
    const location = `${path ?? result.node_id}${
        line !== undefined ? `:${line}` : ""
    }`;
    const hasFailureLocation = Boolean(
        failure?.path || failure?.line !== undefined,
    );
    const editorUrl = failure?.editor_url ?? (
        hasFailureLocation ? undefined : result.editor_url
    );
    const truncatedDetails = phase.truncated?.filter(
        (field) => !["stdout", "stderr", "log"].includes(field),
    ) ?? [];

    if (
        phase.outcome !== "failed"
        && phase.outcome !== "error"
        && !message
        && !longrepr
        && !traceback
    ) {
        return null;
    }

    return (
        <section
            className={`rounded-box border p-4 ${phasePanelClasses(phase.outcome)}`}
        >
            <div className="mb-2 flex flex-wrap items-center gap-2">
                <TestOutcomeIndicator outcome={phase.outcome} />
                <h4 className="font-bold capitalize">{phase.phase} phase</h4>
                {truncatedDetails.length > 0 && (
                    <span
                        className="badge badge-warning badge-sm"
                        title={`Truncated fields: ${truncatedDetails.join(", ")}`}
                    >
                        details truncated
                    </span>
                )}
                {(path || line !== undefined) && (
                    <code className="text-xs opacity-75">
                        <SourceLink
                            editorUrl={editorUrl}
                            label={location}
                        >
                            {location}
                        </SourceLink>
                    </code>
                )}
            </div>
            {message && (
                <p className="mb-2 font-medium whitespace-pre-wrap">
                    {message}
                </p>
            )}
            {longrepr && (
                <pre className="overflow-x-auto whitespace-pre-wrap break-words rounded bg-neutral p-3 text-sm text-neutral-content">
                    {longrepr}
                </pre>
            )}
            {traceback && traceback !== longrepr && (
                <details className="mt-2">
                    <summary className="cursor-pointer font-medium">
                        Traceback
                    </summary>
                    <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words rounded bg-neutral p-3 text-sm text-neutral-content">
                        {traceback}
                    </pre>
                </details>
            )}
            <div className="mt-3">
                <CapturedOutput
                    output={phase}
                    truncated={phase.truncated}
                />
            </div>
        </section>
    );
}

export function ResultDetails({ result }: { result: TestResult }) {
    const phases = result.phases ?? [];
    const directFailure: TestPhaseResult | null = (
        result.failure
        || result.longrepr
    )
        ? {
            phase: result.failure?.phase ?? result.phase ?? "call",
            outcome: result.outcome,
            duration: result.duration,
            failure: result.failure,
            longrepr: result.longrepr,
        }
        : null;
    const detailPhases = phases.filter((phase) => (
        phase.outcome === "failed"
        || phase.outcome === "error"
        || Boolean(phase.reason)
        || Boolean(phase.message)
        || Boolean(phase.longrepr)
        || Boolean(phase.failure)
    ));

    const hasDirectOutput = Boolean(
        result.stdout || result.stderr || result.log,
    );
    const hasPhaseOutput = phases.some(
        (phase) => phase.stdout || phase.stderr || phase.log,
    );
    if (
        detailPhases.length === 0
        && !directFailure
        && !hasDirectOutput
        && !hasPhaseOutput
    ) {
        return null;
    }

    return (
        <div className="mt-3 grid gap-3">
            {(detailPhases.length > 0
                ? detailPhases
                : directFailure ? [directFailure] : []
            ).map((phase) => (
                <PhaseDetail
                    key={`${phase.phase}-${phase.outcome}`}
                    phase={phase}
                    result={result}
                />
            ))}
            {hasDirectOutput && (
                <CapturedOutput
                    output={result}
                    truncated={result.truncated}
                />
            )}
            {phases.map((phase) => {
                const alreadyShown = detailPhases.includes(phase);
                const hasOutput = Boolean(
                    phase.stdout || phase.stderr || phase.log,
                );
                return hasOutput && !alreadyShown
                    ? (
                        <section
                            className="rounded-box border border-base-300 p-3"
                            key={`${phase.phase}-output`}
                        >
                            <h4 className="mb-2 text-sm font-semibold capitalize">
                                {phase.phase} phase output
                            </h4>
                            <CapturedOutput
                                output={phase}
                                truncated={phase.truncated}
                            />
                        </section>
                    )
                    : null;
            })}
        </div>
    );
}

export function ErrorPanel({ error }: { error: TestRunError }) {
    const heading = error.kind === "collection"
        ? "Test collection failed"
        : "pytest could not complete the request";
    const truncatedDiagnostic = error.truncated?.filter(
        (field) => field !== "details" && field !== "source",
    ) ?? [];
    const source = error.source;
    const sourceLine = error.line?.toString() ?? "";
    const sourceGutter = sourceLine
        ? `${" ".repeat(sourceLine.length)} | `
        : "";
    const caret = source && error.column !== undefined
        ? `${source
            .slice(0, Math.max(error.column - 1, 0))
            .replace(/[^\t]/g, " ")}${"^".repeat(Math.max(
            (error.end_column ?? error.column + 1) - error.column,
            1,
        ))}`
        : null;
    const location = `${error.path ?? ""}${
        error.line !== undefined ? `:${error.line}` : ""
    }${error.column !== undefined ? `:${error.column}` : ""}`;
    return (
        <div role="alert" className="alert alert-error items-start text-white">
            <div>
                <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-bold">{heading}</h3>
                    {truncatedDiagnostic.length > 0 && (
                        <span
                            className="badge badge-warning badge-sm"
                            title={`Truncated fields: ${truncatedDiagnostic.join(", ")}`}
                        >
                            diagnostic truncated
                        </span>
                    )}
                </div>
                {(error.path || error.line !== undefined) && (
                    <code className="mb-2 block text-sm">
                        <SourceLink
                            editorUrl={error.editor_url}
                            label={location}
                        >
                            {location}
                        </SourceLink>
                    </code>
                )}
                {source && (
                    <div className="mb-2">
                        <div className="mb-1 flex items-center gap-2 text-sm font-semibold">
                            Source
                            {error.truncated?.includes("source") && (
                                <span className="badge badge-warning badge-sm">
                                    truncated
                                </span>
                            )}
                        </div>
                        <pre
                            aria-label="Syntax error source"
                            className="overflow-x-auto whitespace-pre rounded bg-neutral p-3 text-sm text-neutral-content"
                        >
                            {sourceLine ? `${sourceLine} | ` : ""}
                            {source}
                            {caret && `\n${sourceGutter}${caret}`}
                        </pre>
                    </div>
                )}
                <p className="whitespace-pre-wrap">{error.message}</p>
                {error.details && !source && (
                    <div className="mt-2">
                        <div className="mb-1 flex items-center gap-2 text-sm font-semibold">
                            Details
                            {error.truncated?.includes("details") && (
                                <span className="badge badge-warning badge-sm">
                                    truncated
                                </span>
                            )}
                        </div>
                        <pre className="overflow-x-auto whitespace-pre-wrap break-words rounded bg-neutral p-3 text-sm text-neutral-content">
                            {error.details}
                        </pre>
                    </div>
                )}
            </div>
        </div>
    );
}

const successfulFinishStatuses = new Set(["passed", "collected"]);
const warningFinishStatuses = new Set([
    "cancelled",
    "collection_truncated",
    "interrupted",
    "no_tests",
]);

export function TerminalStatus({
    finishStatus,
    exitCode,
}: {
    finishStatus: string | null;
    exitCode: number | null;
}) {
    const successful = (
        exitCode === null
        || exitCode === 0
    ) && (
        finishStatus === null
        || successfulFinishStatuses.has(finishStatus)
    );
    if (successful) {
        return null;
    }

    const displayStatus = finishStatus
        ? finishStatus.replaceAll("_", " ")
        : "unknown error";
    const warning = finishStatus !== null
        && warningFinishStatuses.has(finishStatus);
    return (
        <div
            className={`alert ${warning ? "alert-warning" : "alert-error text-white"}`}
            role="alert"
        >
            <span>
                pytest finished with status{" "}
                <strong>{displayStatus}</strong>
                {exitCode !== null && ` (exit code ${exitCode})`}.
            </span>
        </div>
    );
}

export function TestRow({
    test,
    result,
    running,
    disabled,
    onRun,
}: {
    test: CollectedTest;
    result?: TestResult;
    running: boolean;
    disabled: boolean;
    onRun: () => void;
}) {
    const duration = formatDuration(result?.duration);
    const editorUrl = result?.editor_url ?? test.editor_url;
    const location = `${test.path ?? ""}${
        test.line !== undefined ? `:${test.line}` : ""
    }`;
    return (
        <article className="rounded-box border border-base-300 bg-base-100 p-4">
            <div className="flex flex-wrap items-start gap-3">
                <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                        {result
                            ? (
                                <TestOutcomeIndicator
                                    outcome={result.outcome}
                                />
                            )
                            : running
                                ? (
                                    <span className="loading loading-spinner loading-xs" />
                                )
                                : <span className="badge badge-ghost">not run</span>}
                        <h3 className="font-mono font-semibold">
                            <SourceLink
                                className="break-all"
                                editorUrl={editorUrl}
                                label={`test ${test.name}`}
                            >
                                {test.name}
                            </SourceLink>
                        </h3>
                        {test.truncated && test.truncated.length > 0 && (
                            <span
                                className="badge badge-warning badge-sm"
                                title={`Truncated fields: ${test.truncated.join(", ")}`}
                            >
                                metadata truncated
                            </span>
                        )}
                        {duration && (
                            <span className="text-xs opacity-60">
                                {duration}
                            </span>
                        )}
                    </div>
                    <code className="mt-1 block break-all text-xs opacity-60">
                        {test.node_id}
                    </code>
                    {(test.path || test.line !== undefined) && (
                        <div className="mt-1 text-xs opacity-60">
                            <SourceLink
                                className="break-all"
                                editorUrl={editorUrl}
                                label={location}
                            >
                                {location}
                            </SourceLink>
                        </div>
                    )}
                    {test.markers && test.markers.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                            {test.markers.map((marker) => (
                                <span
                                    className="badge badge-outline badge-sm"
                                    key={marker}
                                >
                                    @{marker}
                                </span>
                            ))}
                        </div>
                    )}
                </div>
                <button
                    className="btn btn-sm btn-outline btn-primary"
                    disabled={disabled}
                    onClick={onRun}
                    type="button"
                >
                    Run
                </button>
            </div>
            {result && <ResultDetails result={result} />}
        </article>
    );
}

export function ModuleTests() {
    const dispatch = useDispatch();
    const module = useSelector<RootState, ModuleState>(
        (state) => state.module,
    );
    const tests = useSelector<RootState, TestsState>(
        (state) => state.tests,
    );

    useEffect(() => {
        if (!module.selected) {
            return;
        }
        dispatch({ type: "runsocket/disconnect" });
        dispatch({
            type: "testsocket/connect",
            payload: {
                module: module.selected,
                endpoint: `/ws/${module.selected}/tests`,
            },
        });
        return () => {
            dispatch({ type: "testsocket/disconnect" });
        };
    }, [dispatch, module.selected]);

    const busy = tests.status === "collecting"
        || tests.status === "running"
        || tests.status === "cancelling";
    const runningAll = tests.status === "running"
        && tests.requestedNodeIds === null;
    const summary = tests.summary
        ?? (
            Object.keys(tests.results).length > 0
                ? deriveTestSummary(tests.results)
                : null
        );
    const connected = tests.readyState === ReadyState.OPEN;

    return (
        <div className="grid gap-5" aria-live="polite">
            <header className="flex flex-wrap items-start gap-3">
                <div className="min-w-0 flex-1">
                    <h1 className="text-2xl font-bold">Tests</h1>
                </div>
                <div className="flex flex-wrap items-center justify-end gap-2">
                    <label className="label cursor-pointer gap-2 py-0">
                        <span className="label-text">Autorun on changes</span>
                        <input
                            checked={tests.autorun}
                            className="toggle toggle-primary"
                            onChange={(event) => {
                                dispatch(setTestAutorun(event.target.checked));
                            }}
                            type="checkbox"
                        />
                    </label>
                    <button
                        className="btn btn-sm btn-ghost"
                        disabled={!connected || busy}
                        onClick={() => {
                            dispatch({ type: "testsocket/collect" });
                        }}
                        type="button"
                    >
                        Collect
                    </button>
                    {!busy
                        ? (
                            <button
                                className="btn btn-sm btn-primary"
                                disabled={!connected}
                                onClick={() => {
                                    dispatch({ type: "testsocket/run" });
                                }}
                                type="button"
                            >
                                Run All
                            </button>
                        )
                        : (
                            <button
                                className="btn btn-sm btn-error text-white"
                                disabled={tests.status === "cancelling"}
                                onClick={() => {
                                    dispatch({ type: "testsocket/cancel" });
                                }}
                                type="button"
                            >
                                {tests.status === "cancelling"
                                    ? "Cancelling…"
                                    : "Cancel"}
                            </button>
                        )}
                </div>
            </header>

            {tests.autorunPending && (
                <div className="alert alert-info">
                    A source change was detected. Tests will rerun after the
                    current pytest operation finishes.
                </div>
            )}
            {tests.autorunPaused && (
                <div role="alert" className="alert alert-warning">
                    <span>{tests.autorunWarning}</span>
                    <button
                        className="btn btn-sm"
                        onClick={() => {
                            dispatch(resumeTestAutorun());
                            dispatch({
                                type: "testsocket/run",
                                payload: { source: "autorun" },
                            });
                        }}
                        type="button"
                    >
                        Resume and run
                    </button>
                </div>
            )}

            {!connected && tests.status !== "error" && (
                <div className="alert">
                    <span className="loading loading-spinner loading-sm" />
                    Connecting to the pytest runner…
                </div>
            )}
            {tests.status === "collecting" && (
                <div className="alert">
                    <span className="loading loading-spinner loading-sm" />
                    Collecting tests…
                </div>
            )}
            {tests.error && <ErrorPanel error={tests.error} />}
            <TerminalStatus
                exitCode={tests.exitCode}
                finishStatus={tests.finishStatus}
            />
            {summary && (
                <Summary
                    cancelled={tests.cancelled}
                    duration={tests.duration}
                    summary={summary}
                />
            )}

            <section className="grid gap-3" aria-label="Collected tests">
                {tests.collected.map((test) => {
                    const selected = tests.requestedNodeIds;
                    const isRunning = tests.status === "running"
                        && (
                            runningAll
                            || selected?.includes(test.node_id) === true
                        )
                        && !tests.results[test.node_id];
                    return (
                        <TestRow
                            key={test.node_id}
                            onRun={() => {
                                dispatch({
                                    type: "testsocket/run",
                                    payload: { node_ids: [test.node_id] },
                                });
                            }}
                            result={tests.results[test.node_id]}
                            running={isRunning}
                            disabled={busy}
                            test={test}
                        />
                    );
                })}
            </section>

            {connected
                && !busy
                && tests.collected.length === 0
                && !tests.error
                && (
                    <div className="rounded-box border border-dashed border-base-300 p-8 text-center">
                        <h2 className="font-semibold">
                            No tests were collected
                        </h2>
                        <p className="mt-1 text-sm opacity-70">
                            Add pytest test functions or classes to this module,
                            then collect again.
                        </p>
                    </div>
                )}
        </div>
    );
}
