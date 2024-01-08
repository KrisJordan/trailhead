import { ListType } from "../features/module";
import { valueToInlineJSX } from "./helpers";

interface ListUIProps {
    list: ListType
    identifier?: string;
    className?: string;
}

export function DetailsListUI(props: React.PropsWithChildren<ListUIProps>) {
    return <div className="block max-h-96 overflow-y-auto">
        <table className="table border-collapse">
            <thead>
                <tr className="m-0 p-0 text-xl">
                    <th className="width-auto m-0 text-right">Index</th>
                    <th className="w-full m-0">Value</th>
                </tr>
            </thead>
            <tbody>
                {props.list.items.map((item, idx) => <tr>
                    <td className="m-0 py-1 border-y border-y-neutral text-right pr-4 font-bold">{idx}</td>
                    <td className="m-0 py-1 border-y border-y-neutral">{valueToInlineJSX(item, "font-mono")}</td>
                </tr>)}
            </tbody>
        </table>
    </div>;
}