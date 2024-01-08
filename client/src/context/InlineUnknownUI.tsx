import { UnknownType } from "../features/module";

interface UnknownUIProps {
    value: UnknownType;
    name?: string;
    className?: string;
}

export function InlineUnknownUI(props: React.PropsWithChildren<UnknownUIProps>) {
    let value = props.value.value as string;
    return <span><span className={props.className}>{value}</span> ({props.value.python_type})</span>;
}