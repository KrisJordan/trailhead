import { useEffect } from "react";
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

function StatusBadge({ outcome }: { outcome: TestOutcome }) {
    return (
        <span className={`badge badge-sm ${outcomeClasses[outcome]}`}>
            {outcome}
        </span>
    );
}

function Summary({
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

function PhaseFailure({
    phase,
    result,
}: {
    phase: TestPhaseResult;
    result: TestResult;
}) {
    const failure = phase.failure;
    const message = failure?.message ?? phase.message;
    const longrepr = failure?.longrepr ?? phase.longrepr;
    const traceback = failure?.traceback;
    const path = failure?.path ?? result.path;
    const line = failure?.line ?? result.line;

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
        <section className="rounded-box border border-error/40 bg-error/5 p-4">
            <div className="mb-2 flex flex-wrap items-center gap-2">
                <StatusBadge outcome={phase.outcome} />
                <h4 className="font-bold capitalize">{phase.phase} phase</h4>
                {(path || line !== undefined) && (
                    <code className="text-xs opacity-75">
                        {path ?? result.node_id}
                        {line !== undefined ? `:${line}` : ""}
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

function ResultDetails({ result }: { result: TestResult }) {
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
    const failurePhases = phases.filter((phase) => (
        phase.outcome === "failed"
        || phase.outcome === "error"
        || Boolean(phase.message)
        || Boolean(phase.longrepr)
        || Boolean(phase.failure)
    ));

    const hasDirectOutput = Boolean(
        result.stdout || result.stderr || result.log,
    );
    if (
        phases.length === 0
        && !directFailure
        && !hasDirectOutput
    ) {
        return null;
    }

    return (
        <div className="mt-3 grid gap-3">
            {phases.length > 0 && (
                <div className="flex flex-wrap gap-2" aria-label="Test phases">
                    {phases.map((phase) => (
                        <span
                            className="inline-flex items-center gap-1 rounded border border-base-300 px-2 py-1 text-xs"
                            key={phase.phase}
                        >
                            <span className="capitalize">{phase.phase}</span>
                            <StatusBadge outcome={phase.outcome} />
                            {formatDuration(phase.duration) && (
                                <span className="opacity-60">
                                    {formatDuration(phase.duration)}
                                </span>
                            )}
                        </span>
                    ))}
                </div>
            )}
            {(failurePhases.length > 0
                ? failurePhases
                : directFailure ? [directFailure] : []
            ).map((phase) => (
                <PhaseFailure
                    key={`${phase.phase}-${phase.outcome}`}
                    phase={phase}
                    result={result}
                />
            ))}
            {hasDirectOutput && <CapturedOutput output={result} />}
            {phases.map((phase) => {
                const alreadyShown = failurePhases.includes(phase);
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

function ErrorPanel({ error }: { error: TestRunError }) {
    const heading = error.kind === "collection"
        ? "Test collection failed"
        : "pytest could not complete the request";
    return (
        <div role="alert" className="alert alert-error items-start text-white">
            <div>
                <h3 className="font-bold">{heading}</h3>
                {(error.path || error.line !== undefined) && (
                    <code className="mb-2 block text-sm">
                        {error.path}
                        {error.line !== undefined ? `:${error.line}` : ""}
                    </code>
                )}
                <p className="whitespace-pre-wrap">{error.message}</p>
                {error.details && (
                    <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words rounded bg-neutral p-3 text-sm text-neutral-content">
                        {error.details}
                    </pre>
                )}
            </div>
        </div>
    );
}

function TestRow({
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
    return (
        <article className="rounded-box border border-base-300 bg-base-100 p-4">
            <div className="flex flex-wrap items-start gap-3">
                <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                        {result
                            ? <StatusBadge outcome={result.outcome} />
                            : running
                                ? (
                                    <span className="loading loading-spinner loading-xs" />
                                )
                                : <span className="badge badge-ghost">not run</span>}
                        <h3 className="break-all font-mono font-semibold">
                            {test.name}
                        </h3>
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
                            {test.path}
                            {test.line !== undefined ? `:${test.line}` : ""}
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
                    <p className="mt-1 text-sm opacity-70">
                        {tests.collected.length > 0
                            ? `${tests.collected.length} collected in ${module.info?.name ?? module.selected}`
                            : `pytest results for ${module.info?.name ?? module.selected ?? "this module"}`}
                    </p>
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
