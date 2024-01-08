import { PrimitiveUIProps } from "./helpers";

export function InlineStrUI(props: React.PropsWithChildren<PrimitiveUIProps>) {
    let value = props.value.value as string;
    return <span className={props.className}>"{value}"</span>;
}