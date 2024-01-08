import { PrimitiveUIProps } from "./helpers";

export function FloatUI(props: React.PropsWithChildren<PrimitiveUIProps>) {
    let value = props.value.value as number;
    return <span className={props.className}>{value.toString().indexOf(".") > -1 ? value : value.toFixed(1)}</span>;
}