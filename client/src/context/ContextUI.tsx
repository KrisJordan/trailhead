import { useCallback, useEffect, useState } from "react";
import { Context } from "../features/module";
import { valueToDetailsJSX, variableTableEntryJSX } from "./helpers";

interface ContextProps {
    context: Context | null;
}


export function ContextUI(props: React.PropsWithChildren<ContextProps>) {
    const [selected, setSelected] = useState<string | null>(null);
    const [sticky, setSticky] = useState(false);

    useEffect(() => {
        window.addEventListener('scroll', isSticky);
        return () => window.removeEventListener('scroll', isSticky);
    });

    const isSticky = () => {
        if (window.scrollY > 10) {
            setSticky(true);
        } else {
            setSticky(false);
        }
    };

    const wrapEntry = useCallback((key: string, identifier: string, element: JSX.Element) => {
        return <div key={key} onClick={() => setSelected(identifier)} className={selected === identifier ? "bg-base-200 rounded-lg" : "" + " cursor-pointer"}>
            <div className="font-mono ml-2 p-1">
                {element}
            </div>
        </div>;
    }, [selected]);

    if (props.context === null) {
        return null;
    }

    let context: JSX.Element[] | undefined = undefined;
    if (props.context !== null) {
        context = Object.entries(props.context.values).map(([key, value]) => wrapEntry(key, key, variableTableEntryJSX(key, value)));
    }

    let selectedUI: JSX.Element | null = null;
    if (selected !== null) {
        let value = props.context.values[selected];
        let type;
        if (value.type === 'unknown') {
            type = value.python_type;
        } else {
            type = value.type;
        }
        selectedUI = <div className="bg-base-200 p-4 mt-0 md:mt-0 rounded-lg">
            <h2 className="text-xl"><code className="font-bold">{selected}</code>: {type}</h2>
            {valueToDetailsJSX(props.context.values[selected])}
        </div>;
    }

    let contextClass = "lg:grid lg:grid-cols-2 bg-base-100 w-full";
    if (sticky) {
        contextClass += " sticky top-0 shadow rounded border-4 border border-secondary max-h-72 overflow-y-auto";
    }
    return <div className={contextClass}>
        <div className="mx-2">
            {context}
        </div>
        {selectedUI}
    </div>
}