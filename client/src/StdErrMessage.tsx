interface StdErrProps {
    line: string;
}

interface StackTrace {
    type?: string;
    message: string;
    stack_trace: StackFrame[];
}

interface StackFrame {
    filename: string;
    lineno: number;
    name: string;
    line: string;
    end_lineno: number | null;
    colno: number | null;
    end_colno: number | null;
    locals: Record<string, unknown>;
}

interface ValuePreview {
    type: string;
    repr: string;
}

function isValuePreview(value: unknown): value is ValuePreview {
    return typeof value === 'object'
        && value !== null
        && 'type' in value
        && typeof value.type === 'string'
        && 'repr' in value
        && typeof value.repr === 'string';
}

function valueToJSX(value: unknown): JSX.Element {
    if (typeof value === 'boolean') {
        return <span>{value ? 'True' : 'False'}</span>;
    } else if (typeof value === 'string') {
        return <span>{JSON.stringify(value)}</span>;
    } else if (isValuePreview(value)) {
        return <span><strong>{value.type}</strong> {value.repr}</span>;
    }
    return <span>{JSON.stringify(value)}</span>;
}

export function StdErrMessage(props: React.PropsWithChildren<StdErrProps>) {
    try {
        const message = JSON.parse(props.line) as StackTrace;

        const lastIndex = message.stack_trace.length - 1;

        const frames = message.stack_trace.map((frame, index) => {
            const colno = frame.colno ?? 0;
            const endColno = Math.max(frame.end_colno ?? colno + 1, colno + 1);
            let className = "collapse bg-base-200 mt-2";
            if (index !== lastIndex) {
                className += " collapse-arrow";
            } else {
                className += " collapse-open";
            }
            return <div className={className} key={index}>
                <input type="checkbox" />
                <div className="collapse-title font-bold text-secondary">
                    {frame.name.replace('<module>', 'Globals')}
                    <span className="font-light text-secondary italic pl-2">{frame.filename} line {frame.lineno}</span>
                </div>
                <div className="collapse-content">
                    <pre>
                        {frame.lineno.toString().padStart(4, " ")} | {frame.line}
                        {" ".repeat(7 + colno) + "^".repeat(endColno - colno) + "\n"}
                        {index !== lastIndex ? "" : `${message.type}: ${message.message}`}
                    </pre>
                    {Object.keys(frame.locals).length > 0 && <>
                        <h5 className="mb-0">Variables at this point</h5>
                        <table className="table m-0 table-fixed">
                            <thead>
                                <tr>
                                    <th className="w-36">Variable</th>
                                    <th>Value</th>
                                </tr>
                            </thead>
                            <tbody>
                                {Object.keys(frame.locals).map((key) => {
                                    return <tr key={key}>
                                        <td className="font-mono">{key}</td>
                                        <td className="font-mono break-words">{valueToJSX(frame.locals[key])}</td>
                                    </tr>
                                })}
                            </tbody>
                        </table>
                    </>}
                </div>
            </div>;
        });

        if (message.type) {
            return <div className="rounded-box bg-error p-4">
                <h3 className="mt-0 text-error-content font-black">{message.type}: {message.message}</h3>
                <h4 className="text-error-content">Stack</h4>
                {frames}
            </div>;
        } else {
            return <p className="text-error text-xl mb-4 font-bold">{props.line}</p>
        }
    } catch (e) {
        return <p className="text-error text-xl mb-4 font-bold">{props.line}</p>
    }

}
