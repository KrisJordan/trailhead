import { DictType } from "../features/module";
import { valueToInlineJSX } from "./helpers";

interface DictUIProps {
    dict: DictType
    identifier?: string;
    className?: string;
}

export function DetailsDictUI(props: React.PropsWithChildren<DictUIProps>) {
    return <div className="block max-h-96 overflow-y-auto">
        <table className="table border-collapse">
            <thead>
                <tr className="m-0 p-0 text-xl">
                    <th className="width-auto m-0 text-right">Key</th>
                    <th className="w-full m-0">Value</th>
                </tr>
            </thead>
            <tbody>
                {props.dict.keys.map((key, idx) => <tr>
                    <td className="m-0 py-1 border-y border-y-neutral text-right pr-4">{valueToInlineJSX(key, "font-mono")}</td>
                    <td className="m-0 py-1 border-y border-y-neutral">{valueToInlineJSX(props.dict.values[idx], "font-mono")}</td>
                </tr>)}
            </tbody>
        </table>
    </div>;
}