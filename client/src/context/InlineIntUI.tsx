import { PrimitiveUIProps } from "./helpers";

export function IntUI(props: React.PropsWithChildren<PrimitiveUIProps>) {
    const value = props.value.value as number;
    return <span className={props.className}>{value}</span>;
}