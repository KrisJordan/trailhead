import { FunctionType } from "../features/module";

interface FunctionUIProps {
    function: FunctionType;
}

export function InlineFunctionUI(props: React.PropsWithChildren<FunctionUIProps>) {
    const fn = props.function;
    const params = fn.parameters.map((param, idx) => {
        return <span key={param.name}>{idx > 0 ? ', ' : null}{param.name}: {param.type}</span>
    });
    return <span>({params}) -&gt; {fn.return_type}</span>;
}