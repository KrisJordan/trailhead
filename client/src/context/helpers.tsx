import { PythonValue } from "../features/module";
import { InlineBoolUI } from "./InlineBoolUI";
import { FloatUI } from "./InlineFloatUI";
import { InlineFunctionUI } from "./InlineFunctionUI";
import { IntUI } from "./InlineIntUI";
import { InlineListUI } from "./InlineListUI";
import { InlineNoneUI } from "./InlineNoneUI";
import { InlineStrUI } from "./InlineStrUI";
import { PrimitiveType } from "../features/module";
import { InlineDictUI } from "./InlineDictUI";
import { InlineUnknownUI } from "./InlineUnknownUI";
import { DetailsListUI } from "./DetailsListUI";
import { DetailsDictUI } from "./DetailsDictUI";

export interface PrimitiveUIProps {
    value: PrimitiveType;
    identifier?: string;
    className?: string;
}

export const variableTableEntryJSX = (name: string, value: PythonValue) => {
    return <div className="overflow-hidden text-nowrap text-ellipsis"><span className="text-lg">{name}</span> {valueToInlineJSX(value)}</div>;
}

export const valueToInlineJSX = (value: PythonValue, className?: string): JSX.Element => {
    if (className === undefined) {
        className = "rounded p-0.5 bg-neutral text-white";
    }
    switch (value.type) {
        case 'function':
            return <InlineFunctionUI function={value} />;
        case 'str':
            return <InlineStrUI value={value} className={className} />;
        case 'bool':
            return <InlineBoolUI value={value} className={className} />;
        case 'int':
            return <IntUI value={value} className={className} />;
        case 'float':
            return <FloatUI value={value} className={className} />;
        case 'none':
            return <InlineNoneUI className={className} />;
        case 'list':
            return <InlineListUI list={value} className="bg-base-300 p-2 rounded" />;
        case 'dict':
            return <InlineDictUI dict={value} className="bg-base-300 p-2 rounded" />;
        case 'unknown':
            return <span><span className="border rounded border-secondary p-1 bg-neutral text-white">{value.value}</span> ({value.python_type})</span>;
    }
}

export const valueToDetailsJSX = (value: PythonValue): JSX.Element => {
    const className = "rounded p-2 border-4 bg-neutral text-white font-bold text-xl my-4 inline-block min-w-48";
    switch (value.type) {
        case 'function':
            return <InlineFunctionUI function={value} />;
        case 'str':
            return <InlineStrUI value={value} className={className} />;
        case 'bool':
            return <InlineBoolUI value={value} className={className} />;
        case 'int':
            return <IntUI value={value} className={className + " text-right"} />;
        case 'float':
            return <FloatUI value={value} className={className + " text-right"} />;
        case 'none':
            return <InlineNoneUI className={className} />;
        case 'list':
            return <DetailsListUI list={value} className="bg-base-300 p-2 rounded" />;
        case 'dict':
            return <DetailsDictUI dict={value} className="bg-base-300 p-2 rounded" />;
        case 'unknown':
            return <InlineUnknownUI value={value} className={className} />;
    }
}