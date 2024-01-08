import { ListType } from "../features/module";
import { valueToInlineJSX } from "./helpers";

interface ListUIProps {
    list: ListType
    identifier?: string;
    className?: string;
}

export function InlineListUI(props: React.PropsWithChildren<ListUIProps>) {
    const firstThree = props.list.items.slice(0, 3);
    const more = props.list.items.length > 3 ? `, ... ${props.list.items.length - 3} more` : "";
    return <span className={props.className}>
        <span className="font-bold text-xl">[</span>
        {firstThree.map((item, idx) => <span>{idx > 0 ? ', ' : ''} {valueToInlineJSX(item)}</span>)}
        {more}
        <span className="font-bold text-xl">]</span>
    </span>;
}