import { DictType } from "../features/module";
import { valueToInlineJSX } from "./helpers";

interface DictUIProps {
    dict: DictType;
    identifier?: string;
    className?: string;
}

export function InlineDictUI(props: React.PropsWithChildren<DictUIProps>) {
    const firstThreeKeys = props.dict.keys.slice(0, 3);
    const firstThreeValues = props.dict.values.slice(0, 3);
    const more = props.dict.keys.length > 3 ? `, ... ${props.dict.keys.length - 3} more` : "";
    return <span className={props.className}>
        <span className="font-bold text-xl">&#123;</span>
        {firstThreeKeys.map((item, idx) => <span>{idx > 0 ? ', ' : ''} {valueToInlineJSX(item)}: {valueToInlineJSX(firstThreeValues[idx])}</span>)}
        {more}
        <span className="font-bold text-xl">&#125;</span>
    </span>;
}