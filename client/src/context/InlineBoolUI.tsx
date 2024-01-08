import { PrimitiveUIProps } from "./helpers";

export function InlineBoolUI(props: React.PropsWithChildren<PrimitiveUIProps>) {
    return <span className={props.className}>{props.value.value ? "True" : "False"}</span>;
}